import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from src.database import get_db
from src.models.message import Message
from src.models.user import User
from src.middleware.auth import get_current_user

router = APIRouter(prefix="/api/messages", tags=["messages"])

UPLOADS_DIR = Path(__file__).parent.parent.parent / "uploads" / "messages"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMG_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMG_SIZE = 5 * 1024 * 1024  # 5 MB


def _conv_id(a: uuid.UUID, b: uuid.UUID) -> str:
    ids = sorted([str(a), str(b)])
    return f"{ids[0]}_{ids[1]}"


def _msg_out(m: Message) -> dict:
    if m.is_deleted:
        return {
            "id": str(m.id),
            "sender_id": str(m.sender_id),
            "sender_name": m.sender.full_name if m.sender else "",
            "content": "",
            "image_url": None,
            "is_read": m.is_read,
            "is_deleted": True,
            "created_at": m.created_at.isoformat(),
        }
    return {
        "id": str(m.id),
        "sender_id": str(m.sender_id),
        "sender_name": m.sender.full_name if m.sender else "",
        "content": m.content,
        "image_url": f"/uploads/messages/{m.image_path}" if m.image_path else None,
        "is_read": m.is_read,
        "is_deleted": False,
        "created_at": m.created_at.isoformat(),
    }


class SendMessageBody(BaseModel):
    to_user_id: uuid.UUID
    content: str = ""
    image_url: str | None = None


# ── Send text message ─────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def send_message(
    body: SendMessageBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id == body.to_user_id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    if not body.content.strip() and not body.image_url:
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    result = await db.execute(select(User).where(User.id == body.to_user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Recipient not found")

    # Extract filename from image_url if provided
    image_path = None
    if body.image_url:
        image_path = body.image_url.split("/uploads/messages/")[-1] if "/uploads/messages/" in body.image_url else None

    msg = Message(
        sender_id=current_user.id,
        receiver_id=body.to_user_id,
        conversation_id=_conv_id(current_user.id, body.to_user_id),
        content=body.content.strip(),
        image_path=image_path,
    )
    db.add(msg)
    await db.commit()

    result2 = await db.execute(
        select(Message).where(Message.id == msg.id).options(selectinload(Message.sender))
    )
    msg = result2.scalar_one()
    return _msg_out(msg)


# ── Upload image for message ──────────────────────────────────────────────────

@router.post("/upload-image")
async def upload_message_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_IMG_MIME:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, GIF, and WEBP images are allowed.")

    data = await file.read()
    if len(data) > MAX_IMG_SIZE:
        raise HTTPException(status_code=413, detail="Image must be under 5 MB.")

    ext = Path(file.filename or "img").suffix or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    (UPLOADS_DIR / filename).write_bytes(data)

    return {"image_url": f"/uploads/messages/{filename}"}


# ── Delete (soft) a message ───────────────────────────────────────────────────

@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete another user's message")

    msg.is_deleted = True
    # Remove image file if present
    if msg.image_path:
        (UPLOADS_DIR / msg.image_path).unlink(missing_ok=True)
        msg.image_path = None
    await db.commit()


# ── Conversations list ────────────────────────────────────────────────────────

@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Message)
        .where(or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id))
        .options(selectinload(Message.sender), selectinload(Message.receiver))
        .order_by(Message.created_at.desc())
    )
    all_msgs = result.scalars().all()

    seen: dict[str, dict] = {}
    unread_by_conv: dict[str, int] = {}

    for msg in all_msgs:
        cid = msg.conversation_id
        if msg.receiver_id == current_user.id and not msg.is_read:
            unread_by_conv[cid] = unread_by_conv.get(cid, 0) + 1
        if cid not in seen:
            other = msg.receiver if msg.sender_id == current_user.id else msg.sender
            last = "📷 Image" if (msg.image_path and not msg.is_deleted) else ("Deleted message" if msg.is_deleted else msg.content)
            seen[cid] = {
                "conversation_id": cid,
                "other_user_id": str(other.id),
                "other_user_name": other.full_name,
                "last_message": last,
                "last_message_at": msg.created_at.isoformat(),
            }

    return [
        {**conv, "unread_count": unread_by_conv.get(conv["conversation_id"], 0)}
        for conv in seen.values()
    ]


# ── Thread ────────────────────────────────────────────────────────────────────

@router.get("/conversation/{other_user_id}")
async def get_thread(
    other_user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv_id = _conv_id(current_user.id, other_user_id)
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .options(selectinload(Message.sender))
        .order_by(Message.created_at.asc())
    )
    return [_msg_out(m) for m in result.scalars().all()]


# ── Mark read ─────────────────────────────────────────────────────────────────

@router.patch("/read/{other_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    other_user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv_id = _conv_id(current_user.id, other_user_id)
    result = await db.execute(
        select(Message).where(
            and_(
                Message.conversation_id == conv_id,
                Message.receiver_id == current_user.id,
                Message.is_read == False,
            )
        )
    )
    for msg in result.scalars().all():
        msg.is_read = True
    await db.commit()
