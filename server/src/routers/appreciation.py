import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from src.database import get_db
from src.models.appreciation import Appreciation
from src.models.user import User, UserRole
from src.middleware.auth import get_current_user
from src.ai.appreciation_prompt import analyze_feedback
from src.services.credibility_service import compute_and_save_score
from src.services.fraud_service import run_fraud_detection

router = APIRouter(prefix="/api/appreciation", tags=["appreciation"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AppreciationCreate(BaseModel):
    to_user_id: uuid.UUID
    raw_feedback: str


class AppreciationResponse(BaseModel):
    id: uuid.UUID
    from_user_id: uuid.UUID
    from_user_name: str
    raw_feedback: str
    skill_rating: float
    communication_rating: float
    reliability_rating: float
    summary: str
    created_at: str

    model_config = {"from_attributes": True}


class AppreciationAggregates(BaseModel):
    count: int
    avg_skill: float
    avg_communication: float
    avg_reliability: float
    items: list[AppreciationResponse]


class AppreciationCreated(BaseModel):
    appreciation: AppreciationResponse
    ai_ratings: dict


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=AppreciationCreated, status_code=status.HTTP_201_CREATED)
async def submit_appreciation(
    body: AppreciationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only clients can submit appreciations")

    if current_user.id == body.to_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot appreciate yourself")

    if len(body.raw_feedback.strip()) < 10:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Feedback is too short")

    # Verify the recipient exists
    recipient = await db.execute(select(User).where(User.id == body.to_user_id))
    if not recipient.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")

    # AI conversion (with fallback when API is unavailable)
    try:
        ai_result = await analyze_feedback(body.raw_feedback)
    except Exception:
        ai_result = {
            "skill_rating": 5.0,
            "communication_rating": 5.0,
            "reliability_rating": 5.0,
            "summary": body.raw_feedback[:200],
        }

    appreciation = Appreciation(
        to_user_id=body.to_user_id,
        from_user_id=current_user.id,
        raw_feedback=body.raw_feedback,
        skill_rating=ai_result["skill_rating"],
        communication_rating=ai_result["communication_rating"],
        reliability_rating=ai_result["reliability_rating"],
        summary=ai_result["summary"],
    )
    db.add(appreciation)
    await db.commit()
    await db.refresh(appreciation)

    # Recompute credibility score immediately, then apply fraud detection.
    await compute_and_save_score(body.to_user_id)
    await run_fraud_detection(body.to_user_id)

    appreciation_resp = AppreciationResponse(
        id=appreciation.id,
        from_user_id=appreciation.from_user_id,
        from_user_name=current_user.full_name,
        raw_feedback=appreciation.raw_feedback,
        skill_rating=appreciation.skill_rating,
        communication_rating=appreciation.communication_rating,
        reliability_rating=appreciation.reliability_rating,
        summary=appreciation.summary,
        created_at=appreciation.created_at.isoformat(),
    )

    return AppreciationCreated(
        appreciation=appreciation_resp,
        ai_ratings={
            "skill_rating": ai_result["skill_rating"],
            "communication_rating": ai_result["communication_rating"],
            "reliability_rating": ai_result["reliability_rating"],
            "summary": ai_result["summary"],
        },
    )


@router.get("/{user_id}", response_model=AppreciationAggregates)
async def get_appreciations(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Appreciation)
        .where(Appreciation.to_user_id == user_id)
        .options(selectinload(Appreciation.from_user))
        .order_by(Appreciation.created_at.desc())
    )
    rows = result.scalars().all()

    count = len(rows)
    if count == 0:
        return AppreciationAggregates(
            count=0, avg_skill=0.0, avg_communication=0.0, avg_reliability=0.0, items=[]
        )

    avg_skill = sum(r.skill_rating for r in rows) / count
    avg_comm = sum(r.communication_rating for r in rows) / count
    avg_rel = sum(r.reliability_rating for r in rows) / count

    items = [
        AppreciationResponse(
            id=r.id,
            from_user_id=r.from_user_id,
            from_user_name=r.from_user.full_name,
            raw_feedback=r.raw_feedback,
            skill_rating=r.skill_rating,
            communication_rating=r.communication_rating,
            reliability_rating=r.reliability_rating,
            summary=r.summary or "",
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]

    return AppreciationAggregates(
        count=count,
        avg_skill=round(avg_skill, 1),
        avg_communication=round(avg_comm, 1),
        avg_reliability=round(avg_rel, 1),
        items=items,
    )
