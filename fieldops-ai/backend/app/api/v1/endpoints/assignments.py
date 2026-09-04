"""
Smart Technician Assignment REST API Endpoints.
Provides candidate evaluation, recommendation generation, assignment confirmation, and unassign handlers.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import require_roles
from app.models.enums import UserRole
from app.schemas.assignment import (
    AssignmentCreatePayload,
    AssignmentRecommendationResponse,
    AssignmentResponse,
    CandidateTechnicianResponse,
)
from app.schemas.auth import UserResponse
from app.services.assignment_service import AssignmentService

router = APIRouter(tags=["Smart Assignment"])


@router.get(
    "/jobs/{job_id}/candidates",
    response_model=list[CandidateTechnicianResponse],
    status_code=status.HTTP_200_OK,
    summary="Get candidate technicians for a service job",
)
async def get_job_candidates(
    job_id: UUID,
    current_user: UserResponse = Depends(require_roles(UserRole.DISPATCHER, UserRole.ADMINISTRATOR)),
):
    """Returns candidate technicians evaluated against eligibility rules and ranked by score."""
    service = AssignmentService()
    return await service.get_candidates_for_job(job_id)


@router.get(
    "/jobs/{job_id}/recommendation",
    response_model=AssignmentRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Smart Assignment recommendation for a service job",
)
@router.get(
    "/jobs/{job_id}/assignment-recommendations",
    response_model=AssignmentRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Smart Assignment recommendation for a service job (standard REST)",
)
async def get_job_recommendation(
    job_id: UUID,
    current_user: UserResponse = Depends(require_roles(UserRole.DISPATCHER, UserRole.ADMINISTRATOR)),
):
    """Generates transparent rule-based assignment recommendation and records audit event."""
    service = AssignmentService()
    return await service.get_recommendation_for_job(job_id=job_id, actor_id=current_user.id)


@router.post(
    "/jobs/{job_id}/assign",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm technician assignment for a service job",
)
@router.post(
    "/jobs/{job_id}/assign-technician",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm technician assignment for a service job (standard REST)",
)
async def confirm_assignment(
    job_id: UUID,
    payload: AssignmentCreatePayload,
    current_user: UserResponse = Depends(require_roles(UserRole.DISPATCHER)),
):
    """Confirms technician assignment, updates job status to ASSIGNED, and records audit event (Dispatcher only)."""
    service = AssignmentService()
    return await service.confirm_assignment(job_id=job_id, payload=payload, actor_id=current_user.id)


@router.post(
    "/jobs/{job_id}/unassign",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Unassign technician from a service job",
)
@router.post(
    "/jobs/{job_id}/unassign-technician",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Unassign technician from a service job (standard REST)",
)
async def unassign_job(
    job_id: UUID,
    current_user: UserResponse = Depends(require_roles(UserRole.DISPATCHER)),
):
    """Unassigns technician, reverts job status to NEW, and records audit event (Dispatcher only)."""
    service = AssignmentService()
    return await service.unassign_job(job_id=job_id, actor_id=current_user.id)
