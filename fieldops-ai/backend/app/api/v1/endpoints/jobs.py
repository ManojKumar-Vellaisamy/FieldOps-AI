"""
Job Management API v1 Endpoints.
Provides RESTful CRUD operations, filtering, pagination, search, status transitions, cancellation handling, technician queries, and audit logging.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import ForbiddenError
from app.models.enums import UserRole
from app.schemas.auth import UserResponse
from app.schemas.job import (
    JobCancelPayload,
    JobCreate,
    JobResponse,
    JobStatusPatch,
    JobUpdate,
    PaginatedJobResponse,
)
from app.services.job_service import JobService

router = APIRouter(tags=["Job Management"])


@router.get(
    "",
    response_model=PaginatedJobResponse,
    status_code=status.HTTP_200_OK,
    summary="List jobs with search, status, priority, skill, date filters, and pagination",
)
async def list_jobs(
    search: Optional[str] = Query(None, description="Search by job number, customer name, address, description"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (NEW, ASSIGNED, TRAVELLING, ARRIVED, WORKING, COMPLETED, CANCELLED)"),
    priority_filter: Optional[str] = Query(None, alias="priority", description="Filter by priority (LOW, MEDIUM, HIGH, CRITICAL)"),
    required_skill_id: Optional[UUID] = Query(None, description="Filter by required skill UUID"),
    scheduled_date: Optional[str] = Query(None, description="Filter by scheduled date (YYYY-MM-DD)"),
    assignment_status: Optional[str] = Query(None, alias="assignment_status", description="Filter by assignment status (ASSIGNED, UNASSIGNED)"),
    sort_by: str = Query("created_at", description="Sort field (created_at, job_number, scheduled_time, priority)"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    current_user: UserResponse = Depends(get_current_user),
) -> PaginatedJobResponse:
    """List jobs. Accessible by Dispatcher and Administrator roles."""
    if current_user.role == UserRole.TECHNICIAN.value:
        raise ForbiddenError("Technicians are not authorized to view full job directory. Use /api/v1/jobs/my.")

    service = JobService()
    return await service.list_jobs(
        search=search,
        status=status_filter,
        priority=priority_filter,
        required_skill_id=required_skill_id,
        scheduled_date=scheduled_date,
        assignment_status=assignment_status,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/my",
    response_model=list[JobResponse],
    status_code=status.HTTP_200_OK,
    summary="Get jobs assigned to current authenticated technician",
)
async def get_my_jobs(
    current_user: UserResponse = Depends(get_current_user),
) -> list[JobResponse]:
    """Retrieve jobs assigned to authenticated technician profile."""
    service = JobService()
    return await service.get_my_jobs(current_user.id)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get job details by ID",
)
async def get_job(
    job_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> JobResponse:
    """Get single job profile details."""
    service = JobService()
    return await service.get_job_by_id(
        job_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service job",
    dependencies=[Depends(require_roles(UserRole.DISPATCHER))],
)
async def create_job(
    payload: JobCreate,
    current_user: UserResponse = Depends(get_current_user),
) -> JobResponse:
    """Create a new job. Restricted strictly to Dispatcher role."""
    service = JobService()
    return await service.create_job(payload, actor_id=current_user.id)


@router.put(
    "/{job_id}",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Update job details",
    dependencies=[Depends(require_roles(UserRole.DISPATCHER))],
)
async def update_job(
    job_id: UUID,
    payload: JobUpdate,
    current_user: UserResponse = Depends(get_current_user),
) -> JobResponse:
    """Update job details. Restricted strictly to Dispatcher role."""
    service = JobService()
    return await service.update_job(job_id, payload, actor_id=current_user.id)


@router.patch(
    "/{job_id}/status",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Update job lifecycle status",
)
async def patch_job_status(
    job_id: UUID,
    payload: JobStatusPatch,
    current_user: UserResponse = Depends(get_current_user),
) -> JobResponse:
    """Perform validated status transition on a job."""
    service = JobService()
    return await service.patch_status(
        job_id, payload, actor_id=current_user.id, actor_role=current_user.role
    )



@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a job with reason",
    dependencies=[Depends(require_roles(UserRole.DISPATCHER))],
)
async def cancel_job(
    job_id: UUID,
    payload: JobCancelPayload,
    current_user: UserResponse = Depends(get_current_user),
) -> JobResponse:
    """Cancel job with cancellation reason. Restricted strictly to Dispatcher role."""
    service = JobService()
    return await service.cancel_job(job_id, payload, actor_id=current_user.id)
