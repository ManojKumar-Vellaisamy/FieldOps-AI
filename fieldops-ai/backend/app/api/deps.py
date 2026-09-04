"""
FastAPI dependency injection utilities for authentication and RBAC authorization.
"""

from collections.abc import Callable
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import UserRole
from app.schemas.auth import UserResponse
from app.services.auth_service import AuthService

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> UserResponse:
    """
    FastAPI dependency that extracts and validates the Bearer token from headers.
    Returns the authenticated user's profile.
    """
    if not credentials or not credentials.credentials:
        raise UnauthorizedError("Authentication token is missing.")

    payload = decode_access_token(credentials.credentials)
    auth_service = AuthService()
    user = await auth_service.get_user_by_id(payload.sub)
    return user


def require_roles(*allowed_roles: UserRole) -> Callable:
    """
    Factory dependency for Role-Based Access Control (RBAC).

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))])
        async def admin_endpoint():
            ...
    """

    async def role_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if current_user.role not in allowed_roles:
            raise ForbiddenError(
                f"Role '{current_user.role.value}' is not authorized to access this resource."
            )
        return current_user

    return role_checker
