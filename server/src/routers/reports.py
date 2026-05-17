"""
Account report system and admin panel endpoints.

Hirer endpoints:
  POST /api/reports          — submit a report against a candidate profile
  GET  /api/reports/my       — list reports submitted by the current user

Admin endpoints (requires is_admin = true):
  GET  /api/admin/reports        — list all reports
  PUT  /api/admin/reports/{id}/approve — approve → penalise score + suspicious tag
  PUT  /api/admin/reports/{id}/reject  — reject → no effect on score
  GET  /api/admin/users          — list all users
"""
import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.config import settings
from src.models.user import User
from src.models.report import AccountReport, ReportStatus, ReportReason
from src.models.credibility_score import CredibilityScore, FraudRisk
from src.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

reports_router = APIRouter(prefix="/api/reports", tags=["reports"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

# ── Score penalty applied when a report is approved ──────────────────────────
_APPROVED_REPORT_PENALTY = 12

# ── Schemas ───────────────────────────────────────────────────────────────────

class ReportCreate(BaseModel):
    reported_user_id: uuid.UUID
    reason: ReportReason
    evidence_text: Optional[str] = None


class ReportResponse(BaseModel):
    id: uuid.UUID
    reporter_id: uuid.UUID
    reported_user_id: uuid.UUID
    reason: str
    evidence_text: Optional[str]
    status: str
    admin_note: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]
    reporter_name: Optional[str] = None
    reported_user_name: Optional[str] = None


class AdminResolveBody(BaseModel):
    admin_note: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_admin(current_user: User) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user


def _require_super_admin(current_user: User) -> User:
    _require_admin(current_user)
    allowlist = settings.super_admin_email_set
    if not allowlist or current_user.email.lower() not in allowlist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only dedicated super admins can manage admin accounts.",
        )
    return current_user


def _report_to_response(r: AccountReport) -> ReportResponse:
    return ReportResponse(
        id=r.id,
        reporter_id=r.reporter_id,
        reported_user_id=r.reported_user_id,
        reason=r.reason.value,
        evidence_text=r.evidence_text,
        status=r.status.value,
        admin_note=r.admin_note,
        created_at=r.created_at,
        resolved_at=r.resolved_at,
        reporter_name=r.reporter.full_name if r.reporter else None,
        reported_user_name=r.reported_user.full_name if r.reported_user else None,
    )


async def _apply_suspicious_penalty(reported_user_id: uuid.UUID, db: AsyncSession) -> None:
    """Mark score as suspicious and deduct penalty points."""
    result = await db.execute(
        select(CredibilityScore).where(CredibilityScore.user_id == reported_user_id)
    )
    score_row = result.scalar_one_or_none()
    if score_row:
        score_row.is_suspicious = True
        score_row.score = max(0, score_row.score - _APPROVED_REPORT_PENALTY)
        if "Admin-approved report: suspicious account" not in (score_row.authenticity_flags or []):
            score_row.authenticity_flags = (score_row.authenticity_flags or []) + [
                "Admin-approved report: account was flagged as suspicious by a hirer."
            ]
        if score_row.fraud_risk == FraudRisk.low:
            score_row.fraud_risk = FraudRisk.medium
        score_row.computed_at = datetime.utcnow()
        await db.commit()


async def _remove_suspicious_if_no_approved(reported_user_id: uuid.UUID, db: AsyncSession) -> None:
    """Remove suspicious tag if no approved reports remain for this user."""
    count_result = await db.execute(
        select(func.count(AccountReport.id)).where(
            AccountReport.reported_user_id == reported_user_id,
            AccountReport.status == ReportStatus.approved,
        )
    )
    approved_count = count_result.scalar() or 0
    if approved_count == 0:
        result = await db.execute(
            select(CredibilityScore).where(CredibilityScore.user_id == reported_user_id)
        )
        score_row = result.scalar_one_or_none()
        if score_row and score_row.is_suspicious:
            score_row.is_suspicious = False
            score_row.authenticity_flags = [
                f for f in (score_row.authenticity_flags or [])
                if "Admin-approved report" not in f
            ]
            if score_row.fraud_risk == FraudRisk.medium:
                score_row.fraud_risk = FraudRisk.low
            await db.commit()


async def _restore_score_after_reconsider(reported_user_id: uuid.UUID, db: AsyncSession) -> None:
    """Restore the score penalty when an approved report is reconsidered."""
    result = await db.execute(
        select(CredibilityScore).where(CredibilityScore.user_id == reported_user_id)
    )
    score_row = result.scalar_one_or_none()
    if score_row:
        score_row.score = min(100, score_row.score + _APPROVED_REPORT_PENALTY)
        score_row.computed_at = datetime.utcnow()
        await db.commit()


# ── Hirer: submit a report ────────────────────────────────────────────────────

@reports_router.post("", status_code=status.HTTP_201_CREATED)
async def submit_report(
    body: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Can't report yourself
    if current_user.id == body.reported_user_id:
        raise HTTPException(status_code=400, detail="You cannot report your own account.")

    # Check target user exists
    target = await db.execute(select(User).where(User.id == body.reported_user_id))
    if not target.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Reported user not found.")

    # Prevent duplicate pending reports from the same reporter
    existing = await db.execute(
        select(AccountReport).where(
            AccountReport.reporter_id == current_user.id,
            AccountReport.reported_user_id == body.reported_user_id,
            AccountReport.status == ReportStatus.pending,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="You already have a pending report against this account.",
        )

    report = AccountReport(
        reporter_id=current_user.id,
        reported_user_id=body.reported_user_id,
        reason=body.reason,
        evidence_text=body.evidence_text,
    )
    db.add(report)
    await db.commit()
    return {"message": "Report submitted successfully. An admin will review it.", "id": str(report.id)}


@reports_router.get("/my", response_model=list[ReportResponse])
async def get_my_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AccountReport)
        .where(AccountReport.reporter_id == current_user.id)
        .options(selectinload(AccountReport.reporter), selectinload(AccountReport.reported_user))
        .order_by(AccountReport.created_at.desc())
    )
    return [_report_to_response(r) for r in result.scalars().all()]


# ── Admin: list all reports ───────────────────────────────────────────────────

@admin_router.get("/reports", response_model=list[ReportResponse])
async def admin_list_reports(
    filter_status: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    q = select(AccountReport).options(
        selectinload(AccountReport.reporter),
        selectinload(AccountReport.reported_user),
    )
    if filter_status:
        try:
            q = q.where(AccountReport.status == ReportStatus(filter_status))
        except ValueError:
            pass
    q = q.order_by(AccountReport.created_at.desc())
    result = await db.execute(q)
    return [_report_to_response(r) for r in result.scalars().all()]


# ── Admin: approve a report ───────────────────────────────────────────────────

@admin_router.put("/reports/{report_id}/approve")
async def admin_approve_report(
    report_id: uuid.UUID,
    body: AdminResolveBody,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(select(AccountReport).where(AccountReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    if report.status != ReportStatus.pending:
        raise HTTPException(status_code=409, detail=f"Report is already {report.status.value}.")

    report.status = ReportStatus.approved
    report.admin_note = body.admin_note
    report.resolved_at = datetime.utcnow()
    await db.commit()

    # Apply suspicious penalty in background so response is fast
    background_tasks.add_task(_apply_suspicious_penalty, report.reported_user_id, db)

    return {"message": "Report approved. Suspicious tag and score penalty applied."}


# ── Admin: reject a report ────────────────────────────────────────────────────

@admin_router.put("/reports/{report_id}/reject")
async def admin_reject_report(
    report_id: uuid.UUID,
    body: AdminResolveBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(select(AccountReport).where(AccountReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    if report.status != ReportStatus.pending:
        raise HTTPException(status_code=409, detail=f"Report is already {report.status.value}.")

    report.status = ReportStatus.rejected
    report.admin_note = body.admin_note
    report.resolved_at = datetime.utcnow()
    await db.commit()

    return {"message": "Report rejected. No score change."}


# ── Admin: reconsider an approved report ────────────────────────────────────

@admin_router.put("/reports/{report_id}/reconsider")
async def admin_reconsider_report(
    report_id: uuid.UUID,
    body: AdminResolveBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(select(AccountReport).where(AccountReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    if report.status != ReportStatus.approved:
        raise HTTPException(status_code=409, detail=f"Report is not approved (current: {report.status.value}).")

    report.status = ReportStatus.reconsidered
    report.admin_note = body.admin_note
    report.resolved_at = datetime.utcnow()
    await db.commit()

    await _restore_score_after_reconsider(report.reported_user_id, db)
    await _remove_suspicious_if_no_approved(report.reported_user_id, db)

    return {"message": "Report reconsidered. Account restored to normal."}


# ── Admin: list all users ─────────────────────────────────────────────────────

@admin_router.get("/users")
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(
        select(User)
        .options(selectinload(User.credibility_score))
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "uid": u.uid,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "is_suspicious": u.credibility_score.is_suspicious if u.credibility_score else False,
            "score": u.credibility_score.score if u.credibility_score else None,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


# ── Admin: promote/demote admin ───────────────────────────────────────────────

@admin_router.put("/users/{user_id}/set-admin")
async def admin_set_admin(
    user_id: uuid.UUID,
    is_admin: bool = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_super_admin(current_user)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_admin = is_admin
    await db.commit()
    return {"message": f"User {'promoted to' if is_admin else 'removed from'} admin."}
