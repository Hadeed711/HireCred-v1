import uuid
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.user import User
from src.models.profile import Profile
from src.models.credibility_score import CredibilityScore
from src.schemas.profile import ProfileUpdate, ProfileResponse, ScoreResponse
from src.middleware.auth import get_current_user, get_optional_user
from src.services.credibility_service import compute_and_save_score

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _build_profile_response(profile: Profile) -> ProfileResponse:
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        bio=profile.bio,
        title=profile.title,
        location=profile.location,
        skills=profile.skills or [],
        experience=profile.experience or [],
        portfolio=profile.portfolio or [],
        profile_views=profile.profile_views,
        avatar_url=profile.avatar_url,
        proof_signals=profile.proof_signals,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        owner_name=profile.user.full_name,
        owner_email=profile.user.email,
        owner_role=profile.user.role.value,
        owner_uid=profile.user.uid,
    )


async def _resolve_user_id(user_ref: str, db: AsyncSession) -> uuid.UUID:
    """Accept either a numeric uid (e.g. '1001') or a UUID string."""
    try:
        uid = int(user_ref)
        result = await db.execute(select(User).where(User.uid == uid))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
        return user.id
    except ValueError:
        try:
            return uuid.UUID(user_ref)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")


async def _get_profile_with_user(user_id: uuid.UUID, db: AsyncSession) -> Profile:
    result = await db.execute(
        select(Profile)
        .where(Profile.user_id == user_id)
        .options(selectinload(Profile.proof_signals), selectinload(Profile.user))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.get("/{user_ref}/score", response_model=ScoreResponse | None)
async def get_score(user_ref: str, db: AsyncSession = Depends(get_db)):
    user_id = await _resolve_user_id(user_ref, db)
    result = await db.execute(
        select(CredibilityScore).where(CredibilityScore.user_id == user_id)
    )
    score = result.scalar_one_or_none()
    if not score:
        return None
    return ScoreResponse(
        score=score.score,
        strengths=score.strengths or [],
        risks=score.risks or [],
        fraud_risk=score.fraud_risk.value,
        computed_at=score.computed_at,
    )


@router.get("/{user_ref}", response_model=ProfileResponse)
async def get_profile(
    user_ref: str,
    db: AsyncSession = Depends(get_db),
    viewer: Optional[User] = Depends(get_optional_user),
):
    user_id = await _resolve_user_id(user_ref, db)
    profile = await _get_profile_with_user(user_id, db)

    # Don't count views from the profile owner
    if not viewer or viewer.id != user_id:
        profile.profile_views += 1
        await db.commit()

    result = await db.execute(
        select(Profile)
        .where(Profile.id == profile.id)
        .options(selectinload(Profile.proof_signals), selectinload(Profile.user))
    )
    profile = result.scalar_one()
    return _build_profile_response(profile)


@router.put("/{user_id}", response_model=ProfileResponse)
async def update_profile(
    user_id: uuid.UUID,
    body: ProfileUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's profile")

    profile = await _get_profile_with_user(user_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()

    result = await db.execute(
        select(Profile)
        .where(Profile.id == profile.id)
        .options(selectinload(Profile.proof_signals), selectinload(Profile.user))
    )
    profile = result.scalar_one()

    background_tasks.add_task(compute_and_save_score, user_id)

    return _build_profile_response(profile)
