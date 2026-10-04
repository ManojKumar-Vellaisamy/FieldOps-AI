"""
Smart Technician Assignment Service implementing deterministic eligibility validation,
transparent rule-based scoring & ranking, explainability generators, and assignment lifecycle.
"""

from datetime import datetime, timezone
import math
from typing import Optional
import uuid

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.enums import AssignmentType, JobStatus, UserStatus
from app.repositories.assignment_repository import AssignmentRepository
from app.schemas.assignment import (
    AssignmentCreatePayload,
    AssignmentRecommendationResponse,
    AssignmentResponse,
    CandidateTechnicianResponse,
)
from app.core.realtime import (
    ws_manager,
    EVENT_JOB_ASSIGNED,
    EVENT_JOB_UNASSIGNED,
)


def calculate_haversine_distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in miles using Haversine formula."""
    r = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


class AssignmentService:
    """Business service layer for Smart Technician Assignment operations."""

    def __init__(self, repository: AssignmentRepository | None = None) -> None:
        self.repository = repository or AssignmentRepository()

    async def get_candidates_for_job(self, job_id: uuid.UUID) -> list[CandidateTechnicianResponse]:
        """Evaluates all technicians against hard eligibility rules and ranks eligible candidates."""
        job = await self.repository.get_job_by_id(job_id)
        if not job:
            raise NotFoundError("Job", job_id)

        technicians = await self.repository.get_all_technicians()
        evaluated_candidates: list[CandidateTechnicianResponse] = []

        for tech in technicians:
            tech_user = tech.user
            tech_skill = tech.primary_skill

            # 1. Evaluate User Status (Active user account)
            is_user_active = tech_user is not None and tech_user.status == UserStatus.ACTIVE

            # 2. Evaluate Availability Status
            is_available = tech.availability_status.upper() == "AVAILABLE"

            # 3. Evaluate Required Skill Certification (Skill must exist, be ACTIVE, and match job.required_skill_id)
            has_matching_skill = (
                tech.primary_skill_id is not None
                and job.required_skill_id is not None
                and tech.primary_skill_id == job.required_skill_id
                and tech_skill is not None
                and tech_skill.status == "ACTIVE"
            )

            # 4. Evaluate Active Workload (Count of active assignments with status ASSIGNED)
            active_workload_count = sum(
                1 for asg in tech.assignments if getattr(asg, "assignment_status", "") == "ASSIGNED"
            )

            # Determine hard eligibility
            is_eligible = True
            ineligibility_reasons: list[str] = []

            if not is_user_active:
                is_eligible = False
                ineligibility_reasons.append("Inactive user account")
            if not is_available:
                is_eligible = False
                ineligibility_reasons.append(f"Technician status is {tech.availability_status}")
            if not has_matching_skill:
                is_eligible = False
                ineligibility_reasons.append("Required skill not certified")

            # Distance calculation
            distance_display = "Distance unavailable"
            proximity_score = 0.0

            if (
                job.latitude is not None
                and job.longitude is not None
                and tech.current_latitude is not None
                and tech.current_longitude is not None
            ):
                try:
                    dist_miles = calculate_haversine_distance_miles(
                        job.latitude, job.longitude, tech.current_latitude, tech.current_longitude
                    )
                    distance_display = f"{dist_miles:.1f} mi"
                    proximity_score = max(0.0, 10.0 - (dist_miles / 2.0))
                except Exception:
                    distance_display = "Distance unavailable"

            explanation_reasons: list[str] = []
            if is_eligible:
                # Skill match: +40, Availability: +30, Workload score: max(0, 20 - 10*count), Experience: min(years, 10)
                skill_score = 40.0
                avail_score = 30.0
                workload_score = max(0.0, 15.0 - (active_workload_count * 5.0))
                exp_score = min(float(tech.years_experience), 5.0)
                total_raw = skill_score + avail_score + workload_score + exp_score + min(10.0, proximity_score)
                recommendation_score = min(100.0, max(0.0, total_raw))

                explanation_reasons.append("Required skill certified")
                explanation_reasons.append("Available now")
                if active_workload_count == 0:
                    explanation_reasons.append("Lowest active workload")
                else:
                    explanation_reasons.append(f"Current active workload: {active_workload_count} job(s)")
                if distance_display != "Distance unavailable":
                    explanation_reasons.append("Best available proximity")
                elif tech.years_experience > 0:
                    explanation_reasons.append(f"{tech.years_experience} years field experience")
            else:
                recommendation_score = 0.0
                explanation_reasons = ineligibility_reasons

            full_name = tech_user.full_name if tech_user else "Technician"
            primary_skill_name = tech_skill.skill_name if tech_skill else None

            evaluated_candidates.append(
                CandidateTechnicianResponse(
                    technician_id=tech.id,
                    employee_code=tech.employee_code,
                    full_name=full_name,
                    availability_status=tech.availability_status,
                    primary_skill_name=primary_skill_name,
                    years_experience=tech.years_experience,
                    current_workload=active_workload_count,
                    is_eligible=is_eligible,
                    ineligibility_reason=ineligibility_reasons[0] if ineligibility_reasons else None,
                    distance_display=distance_display,
                    recommendation_score=round(recommendation_score, 1),
                    ranking=1,
                    explanation_reasons=explanation_reasons,
                )
            )

        # Sort: Eligible candidates first sorted by recommendation_score descending, then ineligible candidates
        eligible_list = [c for c in evaluated_candidates if c.is_eligible]
        ineligible_list = [c for c in evaluated_candidates if not c.is_eligible]

        eligible_list.sort(key=lambda x: x.recommendation_score, reverse=True)
        ineligible_list.sort(key=lambda x: x.full_name)

        sorted_candidates = eligible_list + ineligible_list
        for idx, candidate in enumerate(sorted_candidates, start=1):
            candidate.ranking = idx

        return sorted_candidates

    async def get_recommendation_for_job(
        self, job_id: uuid.UUID, actor_id: uuid.UUID
    ) -> AssignmentRecommendationResponse:
        """Generates deterministic recommendation calculation and records audit log."""
        job = await self.repository.get_job_by_id(job_id)
        if not job:
            raise NotFoundError("Job", job_id)

        candidates = await self.get_candidates_for_job(job_id)
        eligible_candidates = [c for c in candidates if c.is_eligible]

        recommended_technician: Optional[CandidateTechnicianResponse] = None
        recommendation_score: Optional[float] = None
        explanation: str

        if eligible_candidates:
            recommended_technician = eligible_candidates[0]
            recommendation_score = recommended_technician.recommendation_score
            explanation = (
                f"Recommended {recommended_technician.full_name} based on certified skill match, "
                f"immediate availability, and current workload ranking."
            )
        else:
            explanation = "No eligible technician available for this job."

        alternatives = (
            [c for c in eligible_candidates if c.technician_id != recommended_technician.technician_id]
            if recommended_technician
            else []
        )

        # Record audit event
        await self.repository.log_audit_event(
            actor_id=actor_id,
            action="ASSIGNMENT_RECOMMENDATION_GENERATED",
            entity_id=str(job_id),
            new_value={
                "job_id": str(job_id),
                "job_number": job.job_number,
                "recommended_technician_id": str(recommended_technician.technician_id) if recommended_technician else None,
                "score": recommendation_score,
            },
            reason="Dispatcher requested Smart Assignment recommendation",
        )

        required_skill_name = job.required_skill.skill_name if job.required_skill else None

        return AssignmentRecommendationResponse(
            job_id=job.id,
            job_number=job.job_number,
            customer_name=job.customer_name,
            priority=job.priority.value if hasattr(job.priority, "value") else str(job.priority),
            address=job.address,
            scheduled_time=job.scheduled_time,
            assignment_status=job.status.value if hasattr(job.status, "value") else str(job.status),
            required_skill_name=required_skill_name,
            recommended_technician=recommended_technician,
            recommendation_score=recommendation_score,
            ranked_candidates=candidates,
            alternative_technicians=alternatives,
            explanation=explanation,
            generated_at=datetime.now(timezone.utc),
        )

    async def confirm_assignment(
        self, job_id: uuid.UUID, payload: AssignmentCreatePayload, actor_id: uuid.UUID
    ) -> AssignmentResponse:
        """Confirms technician assignment with atomic transaction & race condition validation."""
        job = await self.repository.get_job_by_id(job_id)
        if not job:
            raise NotFoundError("Job", job_id)

        if job.status == JobStatus.CANCELLED:
            raise BadRequestError("Cannot assign a cancelled job.")
        if job.status == JobStatus.COMPLETED:
            raise BadRequestError("Cannot assign a completed job.")
        if job.status in (JobStatus.ASSIGNED, JobStatus.TRAVELLING, JobStatus.ARRIVED, JobStatus.WORKING):
            raise BadRequestError("Job is already assigned to a technician.")

        # Re-check technician eligibility to prevent stale recommendation race condition
        candidates = await self.get_candidates_for_job(job_id)
        target_candidate = next((c for c in candidates if c.technician_id == payload.technician_id), None)

        if not target_candidate:
            raise NotFoundError("Technician", payload.technician_id)
        if not target_candidate.is_eligible:
            raise ConflictError(
                f"Technician is no longer available ({target_candidate.ineligibility_reason}). "
                "Please refresh recommendations."
            )

        assignment = await self.repository.create_assignment_transaction(
            job_id=job_id,
            technician_id=payload.technician_id,
            assigned_by_user_id=actor_id,
            assignment_type=AssignmentType.SYSTEM,
        )

        tech = await self.repository.get_technician_by_id(payload.technician_id)
        tech_name = tech.user.full_name if tech and tech.user else "Technician"
        tech_user_id = tech.user_id if tech else None

        # Broadcast JOB_ASSIGNED operational event
        await ws_manager.broadcast_operational_event(
            EVENT_JOB_ASSIGNED,
            {
                "assignment_id": str(assignment.id),
                "job_id": str(job.id),
                "job_number": job.job_number,
                "customer_name": job.customer_name,
                "address": job.address,
                "priority": job.priority.value if hasattr(job.priority, "value") else str(job.priority),
                "status": "ASSIGNED",
                "technician_id": str(payload.technician_id),
                "technician_name": tech_name,
                "technician_user_id": str(tech_user_id) if tech_user_id else None,
                "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
            },
            technician_user_id=tech_user_id,
        )

        return AssignmentResponse(
            id=assignment.id,
            job_id=assignment.job_id,
            technician_id=assignment.technician_id,
            assigned_by=assignment.assigned_by,
            assignment_type=assignment.assignment_type.value,
            assignment_status=assignment.assignment_status,
            assigned_at=assignment.assigned_at,
            technician_name=tech_name,
            job_number=job.job_number,
        )

    async def unassign_job(self, job_id: uuid.UUID, actor_id: uuid.UUID) -> dict:
        """Unassigns job safely and reverts state to NEW."""
        job = await self.repository.get_job_by_id(job_id)
        if not job:
            raise NotFoundError("Job", job_id)

        try:
            updated_job = await self.repository.unassign_job_transaction(
                job_id=job_id,
                unassigned_by_user_id=actor_id,
                reason="Dispatcher manually unassigned job",
            )
        except ValueError as exc:
            raise ConflictError(str(exc))

        prior_tech_user_id = getattr(updated_job, "_unassigned_technician_user_id", None)

        # Broadcast JOB_UNASSIGNED operational event
        await ws_manager.broadcast_operational_event(
            EVENT_JOB_UNASSIGNED,
            {
                "job_id": str(updated_job.id),
                "job_number": updated_job.job_number,
                "status": "NEW",
                "unassigned_at": datetime.now(timezone.utc).isoformat(),
            },
            technician_user_id=prior_tech_user_id,
        )

        return {
            "message": f"Job {updated_job.job_number} unassigned successfully.",
            "job_id": str(updated_job.id),
            "job_number": updated_job.job_number,
            "status": updated_job.status.value,
        }
