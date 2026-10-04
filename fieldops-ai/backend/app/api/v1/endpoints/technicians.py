"""
Technician Management API v1 Endpoints.
Provides RESTful CRUD operations, filtering, pagination, search, status updates, skill queries, and audit logging.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import UserRole
from app.schemas.auth import UserResponse
from app.schemas.technician import (
    PaginatedTechnicianResponse,
    TechnicianCreate,
    TechnicianDependencyCheckResponse,
    TechnicianLocationPatch,
    TechnicianResponse,
    TechnicianSkillsResponse,
    TechnicianStatusPatch,
    TechnicianUpdate,
)
from app.services.technician_service import TechnicianService

router = APIRouter(tags=["Technician Management"])


@router.get(
    "",
    response_model=PaginatedTechnicianResponse,
    status_code=status.HTTP_200_OK,
    summary="List technicians with pagination, filtering, search, and sorting",
)
async def list_technicians(
    search: Optional[str] = Query(None, description="Search employee code, name, or email"),
    availability_status: Optional[str] = Query(None, description="Filter by status (AVAILABLE, ON_JOB, OFF_DUTY, etc)"),
    skill_id: Optional[UUID] = Query(None, description="Filter by primary skill UUID"),
    sort_by: str = Query("created_at", description="Sort field (created_at, employee_code, years_experience, name)"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    current_user: UserResponse = Depends(get_current_user),
) -> PaginatedTechnicianResponse:
    """List technicians. Accessible by Administrator, Dispatcher, and self Technician."""
    service = TechnicianService()
    if current_user.role == UserRole.TECHNICIAN.value:
        tech = await service.repo.get_by_user_id(current_user.id)
        if not tech:
            return PaginatedTechnicianResponse(
                items=[], total=0, page=page, page_size=page_size, total_pages=1
            )
        return PaginatedTechnicianResponse(
            items=[TechnicianResponse.model_validate(tech)],
            total=1,
            page=1,
            page_size=page_size,
            total_pages=1,
        )

    return await service.list_technicians(
        search=search,
        availability_status=availability_status,
        skill_id=skill_id,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/me",
    response_model=TechnicianResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated technician profile",
)
async def get_my_technician_profile(
    current_user: UserResponse = Depends(get_current_user),
) -> TechnicianResponse:
    """Retrieve technician profile associated with current authenticated user."""
    service = TechnicianService()
    tech = await service.repo.get_by_user_id(current_user.id)
    if not tech:
        raise NotFoundError("Technician profile for current user", str(current_user.id))
    return TechnicianResponse.model_validate(tech)


@router.get(
    "/{id}",
    response_model=TechnicianResponse,
    status_code=status.HTTP_200_OK,
    summary="Get technician details by ID",
)
async def get_technician(
    id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> TechnicianResponse:
    """Get single technician by UUID. Restricted for Technicians to their own record."""
    service = TechnicianService()
    if current_user.role == UserRole.TECHNICIAN.value:
        my_tech = await service.repo.get_by_user_id(current_user.id)
        if not my_tech or my_tech.id != id:
            raise ForbiddenError("Technicians are only authorized to access their own profile.")
    return await service.get_technician_by_id(id)


@router.get(
    "/{id}/skills",
    response_model=TechnicianSkillsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get technician skill associations by technician ID",
)
async def get_technician_skills(
    id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> TechnicianSkillsResponse:
    """Get technician skill matrix. Restricted for Technicians to their own record."""
    service = TechnicianService()
    if current_user.role == UserRole.TECHNICIAN.value:
        my_tech = await service.repo.get_by_user_id(current_user.id)
        if not my_tech or my_tech.id != id:
            raise ForbiddenError("Technicians are only authorized to access their own skills.")
    return await service.get_technician_skills(id)


@router.post(
    "",
    response_model=TechnicianResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new technician profile and user account",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def create_technician(
    payload: TechnicianCreate,
    current_user: UserResponse = Depends(get_current_user),
) -> TechnicianResponse:
    """Create technician. Restricted to Administrator role."""
    service = TechnicianService()
    return await service.create_technician(payload, actor_id=current_user.id)


@router.put(
    "/{id}",
    response_model=TechnicianResponse,
    status_code=status.HTTP_200_OK,
    summary="Update technician profile details",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def update_technician(
    id: UUID,
    payload: TechnicianUpdate,
    current_user: UserResponse = Depends(get_current_user),
) -> TechnicianResponse:
    """Update technician. Restricted to Administrator role."""
    service = TechnicianService()
    return await service.update_technician(id, payload, actor_id=current_user.id)


@router.patch(
    "/{id}/status",
    response_model=TechnicianResponse,
    status_code=status.HTTP_200_OK,
    summary="Update technician availability status",
)
async def patch_technician_status(
    id: UUID,
    payload: TechnicianStatusPatch,
    current_user: UserResponse = Depends(get_current_user),
) -> TechnicianResponse:
    """Update technician status. Restricted to Administrator or self Technician."""
    service = TechnicianService()
    if current_user.role == UserRole.DISPATCHER.value:
        raise ForbiddenError("Dispatchers are not authorized to modify technician status.")
    if current_user.role == UserRole.TECHNICIAN.value:
        my_tech = await service.repo.get_by_user_id(current_user.id)
        if not my_tech or my_tech.id != id:
            raise ForbiddenError("Technicians are only authorized to update their own status.")
    return await service.patch_status(id, payload, actor_id=current_user.id)


@router.patch(
    "/me/location",
    response_model=TechnicianResponse,
    status_code=status.HTTP_200_OK,
    summary="Update authenticated technician GPS location telemetry",
)
async def patch_my_location(
    payload: TechnicianLocationPatch,
    current_user: UserResponse = Depends(get_current_user),
) -> TechnicianResponse:
    """Update current authenticated technician's live GPS coordinates."""
    service = TechnicianService()
    my_tech = await service.repo.get_by_user_id(current_user.id)
    if not my_tech:
        raise NotFoundError("Technician profile for current user", str(current_user.id))

    return await service.update_location(
        my_tech.id,
        payload.latitude,
        payload.longitude,
        recorded_at=payload.recorded_at,
        actor_id=current_user.id,
    )


@router.post(
    "/{id}/activate",
    response_model=TechnicianResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate a deactivated technician profile and user account",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def activate_technician(
    id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> TechnicianResponse:
    """Activate technician and corresponding user account. Restricted to Administrator role."""
    service = TechnicianService()
    return await service.activate_technician(id, actor_id=current_user.id)


@router.post(
    "/{id}/deactivate",
    response_model=TechnicianResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate an active technician profile and user account",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def deactivate_technician(
    id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> TechnicianResponse:
    """Deactivate technician and corresponding user account. Restricted to Administrator role."""
    service = TechnicianService()
    return await service.deactivate_technician(id, actor_id=current_user.id)


@router.get(
    "/{id}/dependencies",
    response_model=TechnicianDependencyCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check operational dependencies for a technician before deletion",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def check_technician_dependencies(
    id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> TechnicianDependencyCheckResponse:
    """Check if technician has any assignment or operational records. Restricted to Administrator role."""
    service = TechnicianService()
    return await service.check_dependencies(id)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete technician profile if no operational dependencies exist",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def delete_technician(
    id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> None:
    """Permanently delete technician. Restricted to Administrator role. Will fail with 409 if dependencies exist."""
    service = TechnicianService()
    await service.delete_technician(id, actor_id=current_user.id)

