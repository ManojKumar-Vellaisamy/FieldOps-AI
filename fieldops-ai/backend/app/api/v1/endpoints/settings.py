"""
Platform Settings API v1 Router.
Provides protected endpoints for Administrator system configuration management.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import require_roles
from app.models.user import UserRole
from app.schemas.auth import UserResponse
from app.schemas.system_setting import SystemSettingsPayload, SystemSettingsResponse
from app.services.settings_service import SettingsService

router = APIRouter(
    prefix="/settings",
    tags=["Settings"],
)


@router.get(
    "",
    response_model=SystemSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_system_settings(
    current_user: UserResponse = Depends(require_roles(UserRole.ADMINISTRATOR)),
) -> SystemSettingsResponse:
    """Retrieve current system configuration parameters (Administrator authorization required)."""
    service = SettingsService()
    return await service.get_settings()


@router.put(
    "",
    response_model=SystemSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def update_system_settings(
    payload: SystemSettingsPayload,
    current_user: UserResponse = Depends(require_roles(UserRole.ADMINISTRATOR)),
) -> SystemSettingsResponse:
    """Update system configuration parameters (Administrator authorization required)."""
    service = SettingsService()
    return await service.update_settings(payload, actor_id=current_user.id)


@router.post(
    "/reset",
    response_model=SystemSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def reset_system_settings(
    current_user: UserResponse = Depends(require_roles(UserRole.ADMINISTRATOR)),
) -> SystemSettingsResponse:
    """Reset system configuration parameters to factory defaults (Administrator authorization required)."""
    service = SettingsService()
    return await service.reset_defaults(actor_id=current_user.id)


__all__ = ["router"]
