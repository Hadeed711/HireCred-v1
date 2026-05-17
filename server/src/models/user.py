import uuid
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from src.database import Base
import enum


class UserRole(str, enum.Enum):
    candidate = "candidate"
    client = "client"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uid: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, server_default=sa.FetchedValue())
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.candidate, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile: Mapped["Profile"] = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    credibility_score: Mapped["CredibilityScore"] = relationship("CredibilityScore", back_populates="user", uselist=False, cascade="all, delete-orphan")
    appreciations_received: Mapped[list["Appreciation"]] = relationship("Appreciation", foreign_keys="Appreciation.to_user_id", back_populates="to_user", cascade="all, delete-orphan")
    appreciations_given: Mapped[list["Appreciation"]] = relationship("Appreciation", foreign_keys="Appreciation.from_user_id", back_populates="from_user")
    messages_sent: Mapped[list["Message"]] = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    messages_received: Mapped[list["Message"]] = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")
