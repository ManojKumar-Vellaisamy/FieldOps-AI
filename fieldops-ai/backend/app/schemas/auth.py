"""
Pydantic schemas for authentication request/response DTOs.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    """Payload submitted during authentication."""

    email: EmailStr = Field(..., example="admin@fieldops.ai")
    password: str = Field(..., min_length=8, example="password123")
    remember_me: bool = Field(default=False)


class UserResponse(BaseModel):
    """User profile data returned to client."""

    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT Token response after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # in seconds
    user: UserResponse


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str  # user id
    email: EmailStr
    role: UserRole
    exp: int
    iat: int | None = None


class PasswordResetRequest(BaseModel):
    """Request payload for password reset initiation."""

    email: EmailStr
