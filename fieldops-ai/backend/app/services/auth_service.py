"""
Authentication service encapsulating credential verification, token issuance, and user lookup.
"""

from datetime import timedelta
import uuid

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse


class AuthService:
    """Domain service for authentication workflows."""

    def __init__(self, user_repo: UserRepository | None = None) -> None:
        self.user_repo = user_repo or UserRepository()

    async def authenticate(self, payload: LoginRequest) -> TokenResponse:
        """Authenticate user credentials and return signed access token."""
        user = await self.user_repo.get_by_email(payload.email)
        if not user:
            raise UnauthorizedError("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedError("User account is deactivated.")

        if not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password.")

        # Determine token lifetime based on remember_me option
        expires_minutes = (
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 24 * 7
            if payload.remember_me
            else settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        expires_delta = timedelta(minutes=expires_minutes)

        token = create_access_token(
            subject=str(user.id),
            email=user.email,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            expires_delta=expires_delta,
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=int(expires_delta.total_seconds()),
            user=UserResponse.model_validate(user),
        )

    async def get_user_by_id(self, user_id: str | uuid.UUID) -> UserResponse:
        """Retrieve user profile by ID."""
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive.")
        return UserResponse.model_validate(user)
