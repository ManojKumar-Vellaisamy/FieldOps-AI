"""
Context-Aware ETA Engine API v1 Endpoints (Module 11 Upgrade).
Provides RESTful endpoints for retrieving explainable baseline and context-aware ETA calculations,
creating Dispatcher manual ETA overrides with audit tracking, viewing override history, and
benchmarking ETA prediction error performance.

RBAC Enforcement:
- DISPATCHER: Full access to view ETAs, apply manual overrides, and view override history.
- ADMINISTRATOR: Full access to view operational telemetry, audit logs, and experiment benchmarks.
- TECHNICIAN: Strictly restricted to viewing ETA for own assigned jobs. Override actions return 403 Forbidden.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import UserRole
from app.repositories.job_repository import JobRepository
from app.schemas.auth import UserResponse
from app.schemas.eta import (
    ETAExperimentResponse,
    ETAOverrideCreate,
    ETAOverrideResponse,
    ETAResponse,
)
from app.services.eta_experiment_service import ETAExperimentService
from app.services.eta_service import ETAService

router = APIRouter(tags=["Context-Aware ETA Engine"])


@router.get(
    "/experiment",
    response_model=ETAExperimentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ETA prediction error benchmark metrics (Baseline vs Context-Aware)",
)
@router.get(
    "/evaluations",
    response_model=ETAExperimentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ETA prediction error benchmark metrics (alias)",
    include_in_schema=False,
)
async def get_eta_experiment_metrics(
    current_user: UserResponse = Depends(get_current_user),
) -> ETAExperimentResponse:
    """
    Retrieve measurable ETA prediction error benchmarks comparing simple distance baseline against
    the Context-Aware ETA model across normal and non-routine operational transit scenarios.
    """
    service = ETAExperimentService()
    return service.evaluate_experiment()


@router.get(
    "/jobs/{job_id}/eta",
    response_model=ETAResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Context-Aware ETA for a field service job",
)
@router.get(
    "/{job_id}",
    response_model=ETAResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Context-Aware ETA for a field service job (direct path)",
    include_in_schema=False,
)
async def get_job_eta(
    job_id: UUID,
    technician_id: Optional[UUID] = Query(
        None, description="Optional target technician UUID to evaluate prospective travel ETA"
    ),
    weather: Optional[str] = Query(
        None, description="Optional environmental weather condition override (e.g. 'Moderate Rain', 'Clear')"
    ),
    record_audit: bool = Query(
        False, description="Flag indicating whether to record a permanent AuditLog entry for this calculation"
    ),
    current_user: UserResponse = Depends(get_current_user),
) -> ETAResponse:
    """
    Retrieve deterministic baseline and context-aware travel ETA for a service job.

    RBAC Enforcement:
    - DISPATCHER & ADMINISTRATOR: Can view ETA across all operational jobs.
    - TECHNICIAN: Strictly restricted to their own assigned job(s). Access to other jobs returns 403 Forbidden.
    """
    job_repo = JobRepository()

    job = await job_repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", str(job_id))

    if current_user.role == UserRole.TECHNICIAN.value:
        if technician_id is not None:
            raise ForbiddenError("Technicians cannot evaluate ETAs for other technicians.")

        is_assigned = await job_repo.is_technician_assigned_to_job(current_user.id, job_id)
        if not is_assigned:
            raise ForbiddenError("Technicians can only access ETA information for jobs assigned to themselves.")

    service = ETAService()
    return await service.calculate_job_eta(
        job_id=job_id,
        technician_id=technician_id,
        weather_condition=weather,
        actor_id=current_user.id,
        record_audit=record_audit,
    )


@router.post(
    "/jobs/{job_id}/override",
    response_model=ETAOverrideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply Dispatcher manual ETA override for a service job",
)
async def create_dispatcher_eta_override(
    job_id: UUID,
    payload: ETAOverrideCreate,
    current_user: UserResponse = Depends(get_current_user),
) -> ETAOverrideResponse:
    """
    Apply a manual Dispatcher ETA override with mandatory rationale reason.
    Generates an immutable audit log entry (ETA_OVERRIDE_CREATED).

    RBAC Enforcement:
    - DISPATCHER & ADMINISTRATOR: Authorized to create manual ETA overrides.
    - TECHNICIAN: Unauthorized (returns 403 Forbidden).
    """
    if current_user.role not in (UserRole.DISPATCHER.value, UserRole.ADMINISTRATOR.value):
        raise ForbiddenError("Technicians are not authorized to create dispatcher ETA overrides.")

    service = ETAService()
    return await service.create_dispatcher_override(
        job_id=job_id,
        overridden_eta=payload.overridden_eta,
        reason=payload.reason,
        dispatcher_id=current_user.id,
    )


@router.get(
    "/jobs/{job_id}/override-history",
    response_model=list[ETAOverrideResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Dispatcher ETA override audit history for a service job",
)
async def get_job_eta_override_history(
    job_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> list[ETAOverrideResponse]:
    """
    Retrieve historical Dispatcher manual ETA overrides applied to a specific service job.

    RBAC Enforcement:
    - DISPATCHER & ADMINISTRATOR: Full access to view override history.
    - TECHNICIAN: Can view history for own assigned job only. Access to unassigned jobs returns 403 Forbidden.
    """
    job_repo = JobRepository()
    job = await job_repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", str(job_id))

    if current_user.role == UserRole.TECHNICIAN.value:
        is_assigned = await job_repo.is_technician_assigned_to_job(current_user.id, job_id)
        if not is_assigned:
            raise ForbiddenError("Technicians can only access ETA information for jobs assigned to themselves.")

    service = ETAService()
    return await service.get_override_history(job_id)
