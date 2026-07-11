"""
Trust Leaderboard — fully SQL-ranked.

Scalability design (see INFRASTRUCTURE.md → "Leaderboard at 1M users"):
The previous implementation loaded EVERY eligible candidate row into Python
and ranked there — O(total users) memory and time per cache miss. Now the
composite rank score is computed inside PostgreSQL and only the top 20 rows
ever cross the wire. Aggregates (appreciations, proof signals) are joined as
grouped subqueries, so the whole thing is one round trip.

At true 1M scale the next step is precomputing this into a materialized view
or a Redis sorted set refreshed every few minutes — the query below is the
exact definition that view would use.
"""
import asyncio
import time
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, desc

from src.database import get_db
from src.models.user import User, UserRole
from src.models.profile import Profile
from src.models.credibility_score import CredibilityScore, FraudRisk
from src.models.appreciation import Appreciation
from src.models.proof_signal import ProofSignal

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

_cache: dict = {"data": None, "expires_at": 0.0}
_CACHE_TTL = 120  # 2 minutes
_cache_lock = asyncio.Lock()

_TOP_N = 20
_MIN_ENTRIES_FOR_CONFIDENCE = 5


def invalidate_leaderboard_cache() -> None:
    _cache["data"] = None
    _cache["expires_at"] = 0.0


def _leaderboard_stmt():
    """Top-N leaderboard computed entirely in SQL.

    Weights (must match the documented formula):
      credibility 65% + appreciation 20% (10% if medium fraud risk)
      + proof signals (max 5 × 2 pts) + views bonus (max 5 pts).
    """
    appr_sq = (
        select(
            Appreciation.to_user_id.label("user_id"),
            func.count(Appreciation.id).label("appr_count"),
            (
                (
                    func.avg(Appreciation.skill_rating)
                    + func.avg(Appreciation.communication_rating)
                    + func.avg(Appreciation.reliability_rating)
                ) / 3.0
            ).label("avg_rating"),
        )
        .group_by(Appreciation.to_user_id)
        .subquery()
    )

    proof_sq = (
        select(
            Profile.user_id.label("user_id"),
            func.count(ProofSignal.id).label("proof_count"),
        )
        .join(ProofSignal, ProofSignal.profile_id == Profile.id)
        .group_by(Profile.user_id)
        .subquery()
    )

    appr_weight = case(
        (CredibilityScore.fraud_risk == FraudRisk.medium, 0.10),
        else_=0.20,
    )
    proof_count = func.coalesce(proof_sq.c.proof_count, 0)
    views_norm = func.least(Profile.profile_views / 50.0, 10.0)

    rank_score = (
        CredibilityScore.score * 0.65
        + appr_sq.c.avg_rating * 10.0 * appr_weight
        + func.least(proof_count, 5) * 2.0
        + views_norm * 0.5
    ).label("rank_score")

    return (
        select(
            User,
            Profile,
            CredibilityScore,
            appr_sq.c.appr_count,
            appr_sq.c.avg_rating,
            proof_count.label("proof_count"),
            rank_score,
        )
        .join(Profile, Profile.user_id == User.id)
        .join(CredibilityScore, CredibilityScore.user_id == User.id)
        # INNER join = "at least one appreciation" eligibility rule
        .join(appr_sq, appr_sq.c.user_id == User.id)
        .outerjoin(proof_sq, proof_sq.c.user_id == User.id)
        .where(User.role == UserRole.candidate)
        .where(User.is_active == True)
        .where(CredibilityScore.fraud_risk != FraudRisk.high)
        .where(CredibilityScore.score >= 10)
        .order_by(desc("rank_score"))
        .limit(_TOP_N)
    )


@router.get("")
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    now = time.time()
    if _cache["data"] is not None and now < _cache["expires_at"]:
        return _cache["data"]

    async with _cache_lock:
        # Re-check after acquiring lock (another request may have populated it)
        now = time.time()
        if _cache["data"] is not None and now < _cache["expires_at"]:
            return _cache["data"]

        rows = (await db.execute(_leaderboard_stmt())).all()

        insufficient = len(rows) < _MIN_ENTRIES_FOR_CONFIDENCE
        ranked = []
        for i, row in enumerate(rows):
            user: User = row.User
            profile: Profile = row.Profile
            score: CredibilityScore = row.CredibilityScore
            ranked.append({
                "user_id": str(user.id),
                "uid": user.uid,
                "name": user.full_name,
                "skills": (profile.skills or [])[:4],
                "credibility_score": score.score,
                "appreciation_count": int(row.appr_count),
                "avg_ratings": round(float(row.avg_rating or 0), 1),
                "proof_signal_count": int(row.proof_count),
                "fraud_risk": score.fraud_risk.value,
                "rank_score": round(float(row.rank_score), 2),
                "rank": i + 1,
                "insufficient_data": insufficient,
            })

        _cache["data"] = ranked
        _cache["expires_at"] = time.time() + _CACHE_TTL
        return ranked
