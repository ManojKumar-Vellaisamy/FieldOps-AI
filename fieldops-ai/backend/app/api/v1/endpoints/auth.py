"""
Authentication & Session Management Endpoints.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, require_roles
from app.models.user import UserRole
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse, UpdateProfileRequest, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and return JWT token",
)
async def login(payload: LoginRequest) -> TokenResponse:
    """
    Authenticate user using email and password.

    Returns access token, expiration, and user profile data.
    """
    auth_service = AuthService()
    return await auth_service.authenticate(payload)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user profile",
)
async def get_me(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Retrieve current authenticated user's profile details."""
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update authenticated user profile",
)
async def update_me(
    payload: UpdateProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Update current authenticated user's profile details (full_name, phone)."""
    auth_service = AuthService()
    return await auth_service.update_profile(current_user.id, payload)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout user session",
)
async def logout(current_user: UserResponse = Depends(get_current_user)) -> dict[str, str]:  # noqa: ARG001
    """
    Client session logout endpoint.
    Confirms token invalidation on client side.
    """
    return {"message": "Successfully logged out."}


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change password for current authenticated user",
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_user),
) -> dict[str, str]:
    """
    Allow any authenticated user to update their account password.
    Requires current password verification and clears first-login must_change_password flag.
    """
    auth_service = AuthService()
    return await auth_service.change_password(current_user.id, payload)


@router.get(
    "/protected",
    status_code=status.HTTP_200_OK,
    summary="Example RBAC protected endpoint",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.DISPATCHER))],
)
async def protected_example(current_user: UserResponse = Depends(get_current_user)) -> dict[str, str]:
    """
    Demonstrates Role-Based Access Control (RBAC).
    Restricted to Administrator and Dispatcher roles.
    """
    return {
        "message": f"Access granted to {current_user.full_name} with role '{current_user.role.value}'.",
    }

