"""
Skills Management API v1 Endpoints.
Provides RESTful CRUD operations, filtering, pagination, search, status updates, technician association queries, and audit logging.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import ForbiddenError
from app.models.enums import UserRole
from app.schemas.auth import UserResponse
from app.schemas.skill import (
    PaginatedSkillResponse,
    SkillCreate,
    SkillResponse,
    SkillStatusPatch,
    SkillUpdate,
    SkillWithTechniciansResponse,
)
from app.services.skill_service import SkillService

router = APIRouter(tags=["Skills Management"])


@router.get(
    "",
    response_model=PaginatedSkillResponse,
    status_code=status.HTTP_200_OK,
    summary="List skills with pagination, search, category filter, and status filter",
)
async def list_skills(
    search: Optional[str] = Query(None, description="Search by skill name or description"),
    category: Optional[str] = Query(None, description="Filter by category (HVAC, Electrical, Network, etc)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (ACTIVE or INACTIVE)"),
    sort_by: str = Query("created_at", description="Sort field (created_at, skill_name, category)"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    current_user: UserResponse = Depends(get_current_user),
) -> PaginatedSkillResponse:
    """List skills. Accessible by Administrator and Dispatcher."""
    service = SkillService()
    return await service.list_skills(
        search=search,
        category=category,
        status=status_filter,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/me",
    response_model=list[SkillResponse],
    status_code=status.HTTP_200_OK,
    summary="Get skills associated with current authenticated technician",
)
async def get_my_skills(
    current_user: UserResponse = Depends(get_current_user),
) -> list[SkillResponse]:
    """Retrieve skills associated with current user's technician profile."""
    service = SkillService()
    return await service.get_my_skills(current_user.id)


@router.get(
    "/{skill_id}",
    response_model=SkillResponse,
    status_code=status.HTTP_200_OK,
    summary="Get skill details by ID",
)
async def get_skill(
    skill_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> SkillResponse:
    """Get single skill by UUID."""
    service = SkillService()
    return await service.get_skill_by_id(skill_id)


@router.get(
    "/{skill_id}/technicians",
    response_model=SkillWithTechniciansResponse,
    status_code=status.HTTP_200_OK,
    summary="Get technicians qualified for a specific skill",
)
async def get_skill_technicians(
    skill_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> SkillWithTechniciansResponse:
    """Get list of technicians associated with a skill. Accessible by Administrator and Dispatcher."""
    if current_user.role == UserRole.TECHNICIAN.value:
        raise ForbiddenError("Technicians are not authorized to view full skill technician directories.")
    service = SkillService()
    return await service.get_skill_with_technicians(skill_id)


@router.post(
    "",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new skill taxonomy record",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def create_skill(
    payload: SkillCreate,
    current_user: UserResponse = Depends(get_current_user),
) -> SkillResponse:
    """Create skill. Restricted to Administrator role."""
    service = SkillService()
    return await service.create_skill(payload, actor_id=current_user.id)


@router.put(
    "/{skill_id}",
    response_model=SkillResponse,
    status_code=status.HTTP_200_OK,
    summary="Update skill taxonomy details",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def update_skill(
    skill_id: UUID,
    payload: SkillUpdate,
    current_user: UserResponse = Depends(get_current_user),
) -> SkillResponse:
    """Update skill. Restricted to Administrator role."""
    service = SkillService()
    return await service.update_skill(skill_id, payload, actor_id=current_user.id)


@router.patch(
    "/{skill_id}/status",
    response_model=SkillResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate or deactivate a skill (soft deactivation)",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def patch_skill_status(
    skill_id: UUID,
    payload: SkillStatusPatch,
    current_user: UserResponse = Depends(get_current_user),
) -> SkillResponse:
    """Activate/deactivate skill. Restricted to Administrator role."""
    service = SkillService()
    return await service.patch_status(skill_id, payload, actor_id=current_user.id)
