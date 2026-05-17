import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel
from src.models.proof_signal import SignalType


# ── Experience / Portfolio items ─────────────────────────────────────────────

class ExperienceItem(BaseModel):
    id: str = ""
    title: str
    company: str
    start_date: str
    end_date: str | None = None
    current: bool = False
    description: str = ""


class PortfolioItem(BaseModel):
    id: str = ""
    title: str
    description: str = ""
    url: str = ""
    tech_stack: list[str] = []


# ── Proof signals ─────────────────────────────────────────────────────────────

class ProofSignalCreate(BaseModel):
    signal_type: SignalType
    title: str
    url: str | None = None
    description: str | None = None


class ProofSignalResponse(BaseModel):
    id: uuid.UUID
    signal_type: SignalType
    title: str
    url: str | None
    description: str | None
    file_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Profile ───────────────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    bio: str | None = None
    title: str | None = None
    location: str | None = None
    skills: list[str] | None = None
    experience: list[dict[str, Any]] | None = None
    portfolio: list[dict[str, Any]] | None = None
    avatar_url: str | None = None


class ProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    bio: str | None
    title: str | None
    location: str | None
    skills: list[str]
    experience: list[dict[str, Any]]
    portfolio: list[dict[str, Any]]
    profile_views: int
    avatar_url: str | None
    cv_url: str | None = None
    cv_analysis: dict[str, Any] | None = None
    proof_signals: list[ProofSignalResponse]
    created_at: datetime
    updated_at: datetime
    # denormalised owner fields
    owner_name: str
    owner_email: str
    owner_role: str
    owner_uid: int | None = None

    model_config = {"from_attributes": True}


# ── Credibility Score ─────────────────────────────────────────────────────────

class ScoreResponse(BaseModel):
    score: int
    strengths: list[str]
    risks: list[str]
    fraud_risk: str
    computed_at: datetime
    is_suspicious: bool = False
    authenticity_flags: list[str] = []
    cv_match_score: int | None = None
    cv_match_warnings: list[str] = []
    url_warnings: list[str] = []
