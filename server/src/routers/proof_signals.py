import uuid
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.user import User
from src.models.profile import Profile
from src.models.proof_signal import ProofSignal, SignalType
from src.schemas.profile import ProofSignalCreate, ProofSignalResponse
from src.middleware.auth import get_current_user

router = APIRouter(prefix="/api/profile", tags=["proof-signals"])

UPLOADS_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


async def _get_own_profile(user_id: uuid.UUID, current_user: User, db: AsyncSession) -> Profile:
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify another user's profile")
    result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.post("/{user_id}/signals", response_model=ProofSignalResponse, status_code=status.HTTP_201_CREATED)
async def add_proof_signal(
    user_id: uuid.UUID,
    body: ProofSignalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await _get_own_profile(user_id, current_user, db)
    signal = ProofSignal(
        profile_id=profile.id,
        signal_type=body.signal_type,
        title=body.title,
        url=body.url,
        description=body.description,
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal


@router.delete("/{user_id}/signals/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proof_signal(
    user_id: uuid.UUID,
    signal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await _get_own_profile(user_id, current_user, db)
    result = await db.execute(
        select(ProofSignal).where(ProofSignal.id == signal_id, ProofSignal.profile_id == profile.id)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")

    if signal.file_path:
        file_path = UPLOADS_DIR / signal.file_path
        if file_path.exists():
            file_path.unlink()

    await db.delete(signal)
    await db.commit()


@router.post("/{user_id}/signals/upload", response_model=ProofSignalResponse, status_code=status.HTTP_201_CREATED)
async def upload_screenshot_signal(
    user_id: uuid.UUID,
    title: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File type not allowed")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 5 MB limit")

    profile = await _get_own_profile(user_id, current_user, db)

    ext = Path(file.filename or "upload").suffix
    filename = f"{uuid.uuid4()}{ext}"
    dest = UPLOADS_DIR / filename
    dest.write_bytes(contents)

    signal = ProofSignal(
        profile_id=profile.id,
        signal_type=SignalType.screenshot,
        title=title,
        description=description or None,
        file_path=filename,
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal
