import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from src.database import Base
import enum


class ReportStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"   # admin approved → score penalised + suspicious tag
    rejected = "rejected"   # admin rejected → no effect
    reconsidered = "reconsidered"  # admin reversed approval → account normalised


class ReportReason(str, enum.Enum):
    fake_account = "fake_account"
    impersonation = "impersonation"
    fake_credentials = "fake_credentials"
    inappropriate_content = "inappropriate_content"
    spam = "spam"
    other = "other"


class AccountReport(Base):
    __tablename__ = "account_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reported_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason: Mapped[ReportReason] = mapped_column(SAEnum(ReportReason, native_enum=False, length=50), nullable=False)
    evidence_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(SAEnum(ReportStatus, native_enum=False, length=20), default=ReportStatus.pending)
    admin_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    reporter: Mapped["User"] = relationship("User", foreign_keys=[reporter_id])
    reported_user: Mapped["User"] = relationship("User", foreign_keys=[reported_user_id])
