import asyncio
import uuid
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.database import AsyncSessionLocal
from src.models.credibility_score import CredibilityScore, FraudRisk
from src.models.profile import Profile
from src.ai.credibility_prompt import evaluate_profile
from src.services.authenticity_service import check_profile_authenticity, compute_url_warnings
from src.routers.leaderboard import invalidate_leaderboard_cache

# Limit concurrent outbound URL checks to avoid exhausting the connection pool
_URL_CHECK_SEM = asyncio.Semaphore(5)

logger = logging.getLogger(__name__)


def _rule_based_score(profile_data: dict) -> dict:
    """Fallback scoring when Ollama is unavailable. Rewards profile completeness."""
    score = 15
    strengths = []
    risks = []

    auth_flags = profile_data.get("authenticity_flags") or []

    if profile_data.get("bio"):
        bio_words = len(str(profile_data.get("bio") or "").split())
        score += 8 if bio_words >= 50 else 4
        strengths.append("Has a profile bio")
        if bio_words < 15:
            risks.append("Bio is very short")
    else:
        risks.append("No bio provided")

    skills = profile_data.get("skills", [])
    score += min(len(skills) * 2, 10)
    if len(skills) >= 3:
        strengths.append(f"Lists {len(skills)} skills")
    elif len(skills) == 0:
        risks.append("No skills listed")

    experience = profile_data.get("experience", [])
    score += min(len(experience) * 8, 16)
    if len(experience) >= 1:
        strengths.append(f"Has {len(experience)} work experience entr{'y' if len(experience) == 1 else 'ies'}")
    else:
        risks.append("No experience listed")

    portfolio = profile_data.get("portfolio", [])
    score += min(len(portfolio) * 6, 12)
    if len(portfolio) >= 1:
        strengths.append(f"Showcases {len(portfolio)} portfolio project{'s' if len(portfolio) > 1 else ''}")

    proof_signals = profile_data.get("proof_signals", [])
    score += min(len(proof_signals) * 4, 12)
    if len(proof_signals) >= 1:
        strengths.append(f"Submitted {len(proof_signals)} proof signal{'s' if len(proof_signals) > 1 else ''}")
    else:
        risks.append("No proof signals added")

    cv = profile_data.get("cv_analysis") or {}
    if cv.get("is_authentic"):
        score += 6
        strengths.append("CV uploaded and verified")

    return {
        "credibility_score": min(score, 100),
        "strengths": strengths,
        "risks": risks,
        "fraud_flags": [],
    }


async def _check_urls_async(portfolio: list[dict], proof_signals: list[dict]) -> list[str]:
    """Run async URL reachability checks and return human-readable warnings."""
    from src.services.url_checker import check_url
    warnings: list[str] = []

    urls_to_check: list[tuple[str, str]] = []
    for item in portfolio:
        u = item.get("url") or ""
        if u:
            urls_to_check.append((item.get("title", "portfolio item"), u))
    for sig in proof_signals:
        u = sig.get("url") or ""
        if u:
            urls_to_check.append((sig.get("title", "proof signal"), u))

    async def _guarded_check(url: str) -> dict:
        async with _URL_CHECK_SEM:
            return await check_url(url)

    results = await asyncio.gather(
        *[_guarded_check(u) for _, u in urls_to_check],
        return_exceptions=True,
    )
    for (label, url), result in zip(urls_to_check, results):
        if isinstance(result, Exception):
            continue
        if not result.get("reachable"):
            warnings.append(
                f'URL for "{label}" is not reachable: {result.get("note", "unknown error")}.'
            )
        elif result.get("title_suspicious"):
            warnings.append(
                f'URL for "{label}" leads to a dead/parked page (title: "{result.get("page_title", "")}") — '
                "this link may be fake."
            )

    return warnings


async def compute_and_save_score(user_id: uuid.UUID) -> dict | None:
    """
    Open a fresh DB session, load profile, gather evidence, call Ollama
    (with rule-based fallback), apply authenticity penalties, upsert score.
    """
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

            owner_name = profile.user.full_name
            owner_email = profile.user.email

            proof_signals_data = [
                {
                    "signal_type": ps.signal_type.value,
                    "title": ps.title,
                    "url": ps.url,
                    "description": ps.description,
                }
                for ps in profile.proof_signals
            ]

            # ── Step 1: Check whether a CV file is present (no analysis) ───────
            has_cv = bool(profile.cv_file_path)

            # ── Step 2: Authenticity heuristic checks ────────────────────────
            profile_data_for_auth = {
                "bio": profile.bio,
                "title": profile.title,
                "skills": profile.skills or [],
                "experience": profile.experience or [],
                "portfolio": profile.portfolio or [],
            }
            auth_result = check_profile_authenticity(
                profile_data_for_auth,
                owner_email=owner_email,
                owner_name=owner_name,
            )

            # ── Step 3: URL reachability check ────────────────────────────────
            url_warnings_async = await _check_urls_async(
                profile.portfolio or [], proof_signals_data
            )
            url_warnings_format = compute_url_warnings(
                profile.portfolio or [], proof_signals_data
            )
            all_url_warnings = list(dict.fromkeys(url_warnings_async + url_warnings_format))

            # ── Step 4: Build full profile_data for AI scoring ────────────────
            profile_data = {
                "owner_name": owner_name,
                "title": profile.title,
                "location": profile.location,
                "bio": profile.bio,
                "skills": profile.skills or [],
                "experience": profile.experience or [],
                "portfolio": profile.portfolio or [],
                "proof_signals": proof_signals_data,
                "has_cv": has_cv,
                "authenticity_flags": auth_result["flags"],
                "url_warnings": all_url_warnings,
            }

            # ── Step 5: AI scoring (with full evidence context) ───────────────
            try:
                score_data = await asyncio.wait_for(evaluate_profile(profile_data), timeout=10.0)
                if score_data.get("credibility_score") == 0 and not score_data.get("strengths"):
                    raise RuntimeError("AI returned a zero score with no strengths")
            except Exception as exc:
                reason = str(exc).strip() or exc.__class__.__name__
                logger.warning("AI scoring failed for user %s (%s); using rule-based fallback", user_id, reason)
                score_data = _rule_based_score(profile_data)

            # ── Step 6: Apply authenticity penalty on top of AI score ─────────
            raw_score = score_data["credibility_score"]
            auth_penalty = auth_result["penalty"]
            if auth_penalty > 0:
                raw_score = max(0, raw_score - auth_penalty)
                score_data["risks"] = score_data.get("risks", []) + [
                    f"Authenticity penalty ({auth_penalty} pts): " + "; ".join(auth_result["flags"][:2])
                ]

            # ── Step 7: Apply URL warning penalty ─────────────────────────────
            if len(all_url_warnings) >= 1:
                raw_score = max(0, raw_score - min(len(all_url_warnings) * 2, 8))

            score_data["credibility_score"] = max(0, min(100, raw_score))

            # ── Step 8: Determine is_suspicious ──────────────────────────────
            # High-risk = automatically suspicious; medium = suspicious too
            is_suspicious = auth_result["risk_level"] in ("medium", "high")

            # Determine fraud_risk from fraud_flags AND authenticity risk level
            fraud_flags = score_data.get("fraud_flags", [])
            if len(fraud_flags) >= 2 or auth_result["risk_level"] == "high" or auth_penalty >= 25:
                fraud_risk = FraudRisk.high
            elif len(fraud_flags) >= 1 or auth_result["risk_level"] == "medium" or auth_penalty >= 12:
                fraud_risk = FraudRisk.medium
            else:
                fraud_risk = FraudRisk.low

            # ── Step 9: Atomic upsert CredibilityScore ────────────────────────
            upsert_values = {
                "user_id": user_id,
                "score": score_data["credibility_score"],
                "strengths": score_data.get("strengths", []),
                "risks": score_data.get("risks", []),
                "fraud_risk": fraud_risk,
                "fraud_flags": fraud_flags,
                "is_suspicious": is_suspicious,
                "authenticity_flags": auth_result["flags"],
                "cv_match_score": None,
                "cv_match_warnings": [],
                "url_warnings": all_url_warnings,
                "computed_at": datetime.utcnow(),
            }
            upsert_stmt = (
                pg_insert(CredibilityScore)
                .values(**upsert_values)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={k: v for k, v in upsert_values.items() if k != "user_id"},
                )
            )
            await db.execute(upsert_stmt)
            await db.commit()
            invalidate_leaderboard_cache()
            logger.info(
                "Credibility score computed for user %s: %d (authenticity_penalty=%d, has_cv=%s)",
                user_id, score_data["credibility_score"], auth_penalty, has_cv,
            )
            return score_data

        except Exception:
            logger.exception("Failed to compute credibility score for user %s", user_id)
            await db.rollback()
            return None
