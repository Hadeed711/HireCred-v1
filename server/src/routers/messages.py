import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from src.database import get_db
from src.models.message import Message
from src.models.user import User
from src.middleware.auth import get_current_user

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _conv_id(a: uuid.UUID, b: uuid.UUID) -> str:
    """Deterministic conversation key regardless of who sends first."""
    ids = sorted([str(a), str(b)])
    return f"{ids[0]}_{ids[1]}"


class SendMessageBody(BaseModel):
    to_user_id: uuid.UUID
    content: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def send_message(
    body: SendMessageBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id == body.to_user_id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    if not body.content.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    result = await db.execute(select(User).where(User.id == body.to_user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Recipient not found")

    msg = Message(
        sender_id=current_user.id,
        receiver_id=body.to_user_id,
        conversation_id=_conv_id(current_user.id, body.to_user_id),
        content=body.content.strip(),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    return {
        "id": str(msg.id),
        "sender_id": str(msg.sender_id),
        "sender_name": current_user.full_name,
        "content": msg.content,
        "is_read": msg.is_read,
        "created_at": msg.created_at.isoformat(),
    }


@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Message)
        .where(
            or_(
                Message.sender_id == current_user.id,
                Message.receiver_id == current_user.id,
            )
        )
        .options(selectinload(Message.sender), selectinload(Message.receiver))
        .order_by(Message.created_at.desc())
    )
    all_msgs = result.scalars().all()

    # One entry per conversation — most recent message first
    seen: dict[str, dict] = {}
    unread_by_conv: dict[str, int] = {}

    for msg in all_msgs:
        cid = msg.conversation_id
        if msg.receiver_id == current_user.id and not msg.is_read:
            unread_by_conv[cid] = unread_by_conv.get(cid, 0) + 1
        if cid not in seen:
            other = msg.receiver if msg.sender_id == current_user.id else msg.sender
            seen[cid] = {
                "conversation_id": cid,
                "other_user_id": str(other.id),
                "other_user_name": other.full_name,
                "last_message": msg.content,
                "last_message_at": msg.created_at.isoformat(),
            }

    return [
        {**conv, "unread_count": unread_by_conv.get(conv["conversation_id"], 0)}
        for conv in seen.values()
    ]


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
    messages = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "sender_id": str(m.sender_id),
            "sender_name": m.sender.full_name,
            "content": m.content,
            "is_read": m.is_read,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


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
