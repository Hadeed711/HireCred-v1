import time
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.database import get_db
from src.models.user import User, UserRole
from src.models.profile import Profile
from src.models.credibility_score import CredibilityScore
from src.models.appreciation import Appreciation

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

    # Load all active candidates who have both a profile and a credibility score
    result = await db.execute(
        select(User, Profile, CredibilityScore)
        .join(Profile, Profile.user_id == User.id)
        .join(CredibilityScore, CredibilityScore.user_id == User.id)
        .where(User.role == UserRole.candidate)
        .where(User.is_active == True)
    )
    rows = result.all()

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
        count = count or 0
        avg_ratings = ((avg_skill or 0.0) + (avg_comm or 0.0) + (avg_rel or 0.0)) / 3

        rank_score = (
            (score.score * 0.5)
            + (count * 2)
            + (avg_ratings * 3)
            + (profile.profile_views * 0.1)
        )

        entries.append({
            "user_id": str(user.id),
            "uid": user.uid,
            "name": user.full_name,
            "skills": (profile.skills or [])[:3],
            "credibility_score": score.score,
            "appreciation_count": count,
            "avg_ratings": round(avg_ratings, 1),
            "rank_score": rank_score,
        })

    entries.sort(key=lambda x: x["rank_score"], reverse=True)

    ranked = [
        {**entry, "rank": i + 1}
        for i, entry in enumerate(entries[:20])
    ]

    _cache["data"] = ranked
    _cache["expires_at"] = now + _CACHE_TTL
    return ranked
