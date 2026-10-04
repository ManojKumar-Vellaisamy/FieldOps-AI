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
from app.services.settings_service import SettingsService


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

        # Determine token lifetime based on configured system settings & remember_me option
        sys_settings = await SettingsService().get_settings()
        jwt_hours = sys_settings.jwt_expiration_hours
        expires_minutes = (jwt_hours * 60 * 7) if payload.remember_me else (jwt_hours * 60)
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

    async def change_password(
        self,
        user_id: str | uuid.UUID,
        payload: "ChangePasswordRequest",
    ) -> dict[str, str]:
        """Verify current password, hash new password, clear must_change_password flag, and write AuditLog."""
        from app.core.exceptions import ValidationError
        from app.database.session import AsyncSessionLocal
        from app.models.audit_log import AuditLog
        from app.core.security import get_password_hash

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("User not found.")

        if not verify_password(payload.current_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect.")

        if payload.confirm_password and payload.new_password != payload.confirm_password:
            raise ValidationError("New password and confirmation password do not match.")

        new_hash = get_password_hash(payload.new_password)
        await self.user_repo.update_password(user.id, new_hash, must_change_password=False)

        # Log audit entry
        async with AsyncSessionLocal() as session:
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=user.id,
                action="USER_PASSWORD_CHANGED",
                entity="User",
                entity_id=str(user.id),
                reason="User successfully changed their account password",
                old_value="password_hash=[PROTECTED]",
                new_value="password_hash=[PROTECTED], must_change_password=False",
            )
            session.add(audit)
            await session.commit()

        return {"message": "Password changed successfully."}

    async def update_profile(
        self,
        user_id: str | uuid.UUID,
        payload: "UpdateProfileRequest",
    ) -> UserResponse:
        """Update authenticated user's profile and record AuditLog."""
        from app.core.exceptions import NotFoundError, ValidationError
        from app.database.session import AsyncSessionLocal
        from app.models.audit_log import AuditLog

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))

        if payload.full_name is not None and len(payload.full_name.strip()) < 2:
            raise ValidationError("Full name must be at least 2 characters long.")

        old_name = user.full_name
        old_phone = user.phone

        updated_user = await self.user_repo.update_profile(
            user.id,
            full_name=payload.full_name,
            phone=payload.phone,
        )
        if not updated_user:
            raise NotFoundError("User", str(user_id))

        # Log audit entry
        async with AsyncSessionLocal() as session:
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=user.id,
                action="USER_PROFILE_UPDATED",
                entity="User",
                entity_id=str(user.id),
                reason="User updated their account profile details",
                old_value=f"full_name='{old_name}', phone='{old_phone}'",
                new_value=f"full_name='{updated_user.full_name}', phone='{updated_user.phone}'",
            )
            session.add(audit)
            await session.commit()

        return UserResponse.model_validate(updated_user)

