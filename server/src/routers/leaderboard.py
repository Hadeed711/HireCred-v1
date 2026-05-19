import time
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.database import get_db
from src.models.user import User, UserRole
from src.models.profile import Profile
from src.models.credibility_score import CredibilityScore, FraudRisk
from src.models.appreciation import Appreciation
from src.models.proof_signal import ProofSignal

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

_cache: dict = {"data": None, "expires_at": 0.0}
_CACHE_TTL = 120  # 2 minutes


def invalidate_leaderboard_cache() -> None:
    _cache["data"] = None
    _cache["expires_at"] = 0.0


@router.get("")
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    now = time.time()
    if _cache["data"] is not None and now < _cache["expires_at"]:
        return _cache["data"]

    # Load candidates with profiles and scores
    result = await db.execute(
        select(User, Profile, CredibilityScore)
        .join(Profile, Profile.user_id == User.id)
        .join(CredibilityScore, CredibilityScore.user_id == User.id)
        .where(User.role == UserRole.candidate)
        .where(User.is_active == True)
        # Exclude high fraud risk
        .where(CredibilityScore.fraud_risk != FraudRisk.high)
        # Minimum credibility gate
        .where(CredibilityScore.score >= 10)
    )
    rows = result.all()

    # Get proof signal counts per candidate
    all_user_ids = [user.id for user, _, _ in rows]
    proof_counts: dict = {}
    if all_user_ids:
        pc_result = await db.execute(
            select(Profile.user_id, func.count(ProofSignal.id).label("cnt"))
            .join(ProofSignal, ProofSignal.profile_id == Profile.id)
            .where(Profile.user_id.in_(all_user_ids))
            .group_by(Profile.user_id)
        )
        proof_counts = {row.user_id: int(row.cnt) for row in pc_result.all()}

    entries = []
    for user, profile, score in rows:
        appr_result = await db.execute(
            select(
                func.count(Appreciation.id),
                func.avg(Appreciation.skill_rating),
                func.avg(Appreciation.communication_rating),
                func.avg(Appreciation.reliability_rating),
            ).where(Appreciation.to_user_id == user.id)
        )
        count, avg_skill, avg_comm, avg_rel = appr_result.one()
        count = int(count or 0)
        avg_ratings = ((avg_skill or 0.0) + (avg_comm or 0.0) + (avg_rel or 0.0)) / 3

        # Require at least 1 appreciation to appear on leaderboard
        if count < 1:
            continue

        # Appreciation component is halved for medium fraud risk
        appr_weight = 0.125 if score.fraud_risk == FraudRisk.medium else 0.25

        proof_count = proof_counts.get(user.id, 0)

        # Normalise views to 0–10 scale (capped at 500 views = 10)
        views_norm = min(profile.profile_views / 50.0, 10.0)

        # Appreciation count contribution (capped at 20 reviews = 10)
        count_norm = min(count / 2.0, 10.0)

        # Composite score (all components normalised to ~0–100)
        rank_score = (
            score.score * 0.40                       # credibility: 0–100 → max 40
            + avg_ratings * 10 * appr_weight         # avg 0–10 → 0–100 × weight → max 25
            + count_norm * 10 * 0.10                 # count → 0–100 × 0.10 → max 10
            + min(proof_count * 3, 30) * 0.50        # proof 0–10 → 0–30 → max 15
            + views_norm * 10 * 0.10                 # views → 0–100 × 0.10 → max 10
        )

        entries.append({
            "user_id": str(user.id),
            "uid": user.uid,
            "name": user.full_name,
            "skills": (profile.skills or [])[:4],
            "credibility_score": score.score,
            "appreciation_count": count,
            "avg_ratings": round(avg_ratings, 1),
            "proof_signal_count": proof_count,
            "fraud_risk": score.fraud_risk.value,
            "rank_score": round(rank_score, 2),
        })

    entries.sort(key=lambda x: x["rank_score"], reverse=True)

    # Build response
    insufficient = len(entries) < 5
    ranked = [
        {**entry, "rank": i + 1, "insufficient_data": insufficient}
        for i, entry in enumerate(entries[:20])
    ]

    _cache["data"] = ranked
    _cache["expires_at"] = now + _CACHE_TTL
    return ranked
