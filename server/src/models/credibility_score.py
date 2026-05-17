import uuid
from datetime import datetime
from sqlalchemy import Integer, Text, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.database import Base
import enum


class FraudRisk(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class CredibilityScore(Base):
    __tablename__ = "credibility_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    strengths: Mapped[list[str]] = mapped_column(JSONB, default=list)
    risks: Mapped[list[str]] = mapped_column(JSONB, default=list)
    fraud_risk: Mapped[FraudRisk] = mapped_column(SAEnum(FraudRisk), default=FraudRisk.low)
    fraud_flags: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # Authenticity / fake-detection
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False)
    authenticity_flags: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # CV ↔ profile match
    cv_match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cv_match_warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # URL reachability warnings from portfolio / proof signals
    url_warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="credibility_score")
