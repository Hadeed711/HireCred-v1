import uuid
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database import AsyncSessionLocal
from src.models.credibility_score import CredibilityScore
from src.models.profile import Profile
from src.ai.credibility_prompt import evaluate_profile
from src.routers.leaderboard import invalidate_leaderboard_cache

logger = logging.getLogger(__name__)


def _rule_based_score(profile_data: dict) -> dict:
    """Fallback scoring when Ollama is unavailable. Rewards profile completeness."""
    score = 20
    strengths = []
    risks = []

    if profile_data.get("bio"):
        score += 10
        strengths.append("Has a profile bio")
    else:
        risks.append("No bio provided")

    skills = profile_data.get("skills", [])
    score += min(len(skills) * 3, 15)
    if len(skills) >= 3:
        strengths.append(f"Lists {len(skills)} skills")
    elif len(skills) == 0:
        risks.append("No skills listed")

    experience = profile_data.get("experience", [])
    score += min(len(experience) * 10, 20)
    if len(experience) >= 1:
        strengths.append(f"Has {len(experience)} work experience entr{'y' if len(experience) == 1 else 'ies'}")
    else:
        risks.append("No experience listed")

    portfolio = profile_data.get("portfolio", [])
    score += min(len(portfolio) * 8, 16)
    if len(portfolio) >= 1:
        strengths.append(f"Showcases {len(portfolio)} portfolio project{'s' if len(portfolio) > 1 else ''}")

    proof_signals = profile_data.get("proof_signals", [])
    score += min(len(proof_signals) * 5, 15)
    if len(proof_signals) >= 1:
        strengths.append(f"Submitted {len(proof_signals)} proof signal{'s' if len(proof_signals) > 1 else ''}")
    else:
        risks.append("No proof signals added")

    if profile_data.get("cv_analysis", {}).get("is_authentic"):
        score += 4
        strengths.append("CV uploaded and verified")

    return {
        "credibility_score": min(score, 100),
        "strengths": strengths,
        "risks": risks,
    }


async def compute_and_save_score(user_id: uuid.UUID) -> dict | None:
    """Open a fresh DB session, load profile, call Ollama (with rule-based fallback), upsert score."""
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Profile)
                .where(Profile.user_id == user_id)
                .options(selectinload(Profile.proof_signals), selectinload(Profile.user))
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return None

            profile_data = {
                "owner_name": profile.user.full_name,
                "title": profile.title,
                "location": profile.location,
                "bio": profile.bio,
                "skills": profile.skills or [],
                "experience": profile.experience or [],
                "portfolio": profile.portfolio or [],
                "proof_signals": [
                    {
                        "signal_type": ps.signal_type.value,
                        "title": ps.title,
                        "url": ps.url,
                        "description": ps.description,
                    }
                    for ps in profile.proof_signals
                ],
                "cv_analysis": profile.cv_analysis,
            }

            try:
                score_data = await evaluate_profile(profile_data)
                if score_data.get("credibility_score") == 0 and not score_data.get("strengths"):
                    raise RuntimeError("AI returned a zero score with no strengths")
            except Exception as exc:
                reason = str(exc).strip() or exc.__class__.__name__
                logger.warning("AI scoring failed for user %s (%s); using rule-based fallback", user_id, reason)
                score_data = _rule_based_score(profile_data)

            score_result = await db.execute(
                select(CredibilityScore).where(CredibilityScore.user_id == user_id)
            )
            score_row = score_result.scalar_one_or_none()

            if score_row:
                score_row.score = score_data["credibility_score"]
                score_row.strengths = score_data["strengths"]
                score_row.risks = score_data["risks"]
                score_row.computed_at = datetime.utcnow()
            else:
                score_row = CredibilityScore(
                    user_id=user_id,
                    score=score_data["credibility_score"],
                    strengths=score_data["strengths"],
                    risks=score_data["risks"],
                )
                db.add(score_row)

            await db.commit()
            invalidate_leaderboard_cache()
            logger.info("Credibility score computed for user %s: %d", user_id, score_data["credibility_score"])
            return score_data

        except Exception:
            logger.exception("Failed to compute credibility score for user %s", user_id)
            await db.rollback()
            return None
