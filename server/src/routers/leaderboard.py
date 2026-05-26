import asyncio
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
_cache_lock = asyncio.Lock()


def invalidate_leaderboard_cache() -> None:
    _cache["data"] = None
    _cache["expires_at"] = 0.0


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

        result = await db.execute(
            select(User, Profile, CredibilityScore)
            .join(Profile, Profile.user_id == User.id)
            .join(CredibilityScore, CredibilityScore.user_id == User.id)
            .where(User.role == UserRole.candidate)
            .where(User.is_active == True)
            .where(CredibilityScore.fraud_risk != FraudRisk.high)
            .where(CredibilityScore.score >= 10)
        )
        rows = result.all()
        all_user_ids = [user.id for user, _, _ in rows]

        # Batch load proof signal counts (single query)
        proof_counts: dict = {}
        if all_user_ids:
            pc_result = await db.execute(
                select(Profile.user_id, func.count(ProofSignal.id).label("cnt"))
                .join(ProofSignal, ProofSignal.profile_id == Profile.id)
                .where(Profile.user_id.in_(all_user_ids))
                .group_by(Profile.user_id)
            )
            proof_counts = {row.user_id: int(row.cnt) for row in pc_result.all()}

        # Batch load appreciation aggregates (single query — was N+1)
        appr_map: dict = {}
        if all_user_ids:
            appr_result = await db.execute(
                select(
                    Appreciation.to_user_id,
                    func.count(Appreciation.id).label("cnt"),
                    func.avg(Appreciation.skill_rating).label("avg_skill"),
                    func.avg(Appreciation.communication_rating).label("avg_comm"),
                    func.avg(Appreciation.reliability_rating).label("avg_rel"),
                )
                .where(Appreciation.to_user_id.in_(all_user_ids))
                .group_by(Appreciation.to_user_id)
            )
            for r in appr_result.all():
                appr_map[r.to_user_id] = {
                    "count": int(r.cnt),
                    "avg": (
                        (float(r.avg_skill or 0) + float(r.avg_comm or 0) + float(r.avg_rel or 0)) / 3
                    ),
                }

        entries = []
        for user, profile, score in rows:
            appr = appr_map.get(user.id)
            count = appr["count"] if appr else 0
            avg_ratings = appr["avg"] if appr else 0.0

            if count < 1:
                continue

            # credibility score is the primary signal (65%)
            # appreciation is secondary (20%, halved for medium fraud risk)
            # proof signals and views are small bonuses (10% + 5%)
            appr_weight = 0.10 if score.fraud_risk == FraudRisk.medium else 0.20
            proof_count = proof_counts.get(user.id, 0)
            views_norm = min(profile.profile_views / 50.0, 10.0)

            rank_score = (
                score.score * 0.65
                + avg_ratings * 10 * appr_weight
                + min(proof_count, 5) * 2.0
                + views_norm * 0.5
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

        insufficient = len(entries) < 5
        ranked = [
            {**entry, "rank": i + 1, "insufficient_data": insufficient}
            for i, entry in enumerate(entries[:20])
        ]

        _cache["data"] = ranked
        _cache["expires_at"] = time.time() + _CACHE_TTL
        return ranked
