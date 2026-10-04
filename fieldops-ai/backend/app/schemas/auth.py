"""
Pydantic schemas for authentication request/response DTOs.
"""

from datetime import datetime
from typing import Optional
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
    phone: Optional[str] = None
    is_active: bool
    must_change_password: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    """Request payload for updating current user profile."""

    full_name: Optional[str] = Field(None, min_length=2, max_length=255, description="Full name of user")
    phone: Optional[str] = Field(None, max_length=50, description="Contact phone number")


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


class ChangePasswordRequest(BaseModel):
    """Request payload for authenticated user password change."""

    current_password: str = Field(..., min_length=1, description="Existing password")
    new_password: str = Field(..., min_length=8, description="New password meeting complexity rules")
    confirm_password: Optional[str] = Field(None, min_length=8, description="Must match new password")
