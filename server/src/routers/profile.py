import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.user import User, UserRole
from src.models.profile import Profile
from src.models.credibility_score import CredibilityScore
from src.schemas.profile import ProfileUpdate, ProfileResponse, ScoreResponse
from src.middleware.auth import get_current_user, get_optional_user
from src.rate_limiter import limiter
from src.services.task_manager import schedule_rescore
from src.services.validation_service import validate_full_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])

UPLOADS_DIR = Path(__file__).parent.parent.parent / "uploads"
CV_DIR = UPLOADS_DIR / "cv"
CV_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_CV_MIME = {"application/pdf"}
MAX_CV_SIZE = 5 * 1024 * 1024  # 5 MB




def _build_profile_response(profile: Profile, is_owner: bool = False) -> ProfileResponse:
    cv_url = f"/uploads/cv/{profile.cv_file_path}" if profile.cv_file_path else None
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
        cv_url=cv_url,
        cv_analysis=profile.cv_analysis,
        proof_signals=profile.proof_signals,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        owner_name=profile.user.full_name,
        owner_email=profile.user.email if is_owner else None,
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
        is_suspicious=score.is_suspicious,
        authenticity_flags=score.authenticity_flags or [],
        cv_match_score=score.cv_match_score,
        cv_match_warnings=score.cv_match_warnings or [],
        url_warnings=score.url_warnings or [],
    )


@router.get("/{user_ref}", response_model=ProfileResponse)
async def get_profile(
    user_ref: str,
    db: AsyncSession = Depends(get_db),
    viewer: Optional[User] = Depends(get_optional_user),
):
    user_id = await _resolve_user_id(user_ref, db)

    is_owner = viewer is not None and viewer.id == user_id
    if not is_owner:
        # Atomic increment — a plain `profile.profile_views += 1` is a
        # read-modify-write race that loses counts under concurrent views.
        await db.execute(
            update(Profile)
            .where(Profile.user_id == user_id)
            .values(profile_views=Profile.profile_views + 1)
        )
        await db.commit()

    profile = await _get_profile_with_user(user_id, db)
    return _build_profile_response(profile, is_owner=is_owner)


@router.put("/{user_id}", response_model=ProfileResponse)
async def update_profile(
    user_id: uuid.UUID,
    body: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's profile")

    profile = await _get_profile_with_user(user_id, db)

    update_data = body.model_dump(exclude_unset=True)

    # Validate but NEVER block — collect warnings for the response
    validation_input = {
        "bio": update_data.get("bio") or profile.bio or "",
        "experience": update_data.get("experience") or profile.experience or [],
        "portfolio": update_data.get("portfolio") or profile.portfolio or [],
    }
    validation_warnings = [e.message for e in validate_full_profile(validation_input)]

    for field, value in update_data.items():
        setattr(profile, field, value)

    # Explicitly mark JSONB/ARRAY fields as modified so SQLAlchemy
    # always emits an UPDATE even when the value reference is unchanged.
    from sqlalchemy.orm.attributes import flag_modified
    for mutable_field in ("skills", "experience", "portfolio"):
        if mutable_field in update_data:
            flag_modified(profile, mutable_field)

    await db.commit()

    # Refresh from DB to build response from committed data, not the identity-map cache
    await db.refresh(profile, ["skills", "experience", "portfolio", "bio", "title", "location"])

    result = await db.execute(
        select(Profile)
        .where(Profile.id == profile.id)
        .options(selectinload(Profile.proof_signals), selectinload(Profile.user))
    )
    profile = result.scalar_one()

    schedule_rescore(user_id)

    response = _build_profile_response(profile, is_owner=True)
    if validation_warnings:
        from fastapi.responses import JSONResponse
        resp_data = response.model_dump(mode="json")
        resp_data["_warnings"] = validation_warnings
        return JSONResponse(content=resp_data)
    return response


@router.post("/{user_id}/cv")
async def upload_cv(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's profile")

    if current_user.role != UserRole.candidate:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only candidates can upload a CV")

    if file.content_type not in ALLOWED_CV_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are accepted for CV upload.",
        )

    data = await file.read()
    if len(data) > MAX_CV_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CV file must be under 5 MB.",
        )

    # Content-Type headers and filenames are client-controlled — verify the
    # actual bytes are a PDF (magic number) before persisting.
    if not data.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content is not a valid PDF.",
        )

    # Server-chosen filename — never derived from client input.
    filename = f"{user_id}.pdf"
    dest = CV_DIR / filename
    await asyncio.to_thread(dest.write_bytes, data)

    # Persist to profile
    result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    # Remove old CV file if name changed
    if profile.cv_file_path and profile.cv_file_path != filename:
        (CV_DIR / profile.cv_file_path).unlink(missing_ok=True)

    profile.cv_file_path = filename
    profile.cv_analysis = None
    await db.commit()

    schedule_rescore(user_id)

    return {
        "cv_url": f"/uploads/cv/{filename}",
        "message": "CV uploaded successfully.",
    }


@router.delete("/{user_id}/cv", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's profile")

    result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    if profile.cv_file_path:
        (CV_DIR / profile.cv_file_path).unlink(missing_ok=True)

    profile.cv_file_path = None
    profile.cv_analysis = None
    await db.commit()

    schedule_rescore(user_id)


@router.post("/{user_id}/rescore", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def rescore_profile(
    request: Request,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger credibility score recomputation for the authenticated user."""
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot rescore another user's profile")
    schedule_rescore(user_id)
    return {"message": "Score recomputation started."}
