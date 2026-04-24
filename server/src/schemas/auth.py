import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
from src.models.user import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.candidate


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # Allow local/dev domains used by seeded demo accounts (e.g. @seed.local).
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("Invalid email format")
        return email


class UserResponse(BaseModel):
    id: uuid.UUID
    uid: int | None = None
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
