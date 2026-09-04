"""
Job Service Layer managing business workflows, coordinate validations, active skill checks, lifecycle transitions, and transaction orchestration.
"""

import math
from typing import Optional
import uuid

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError, ValidationError
from app.models.enums import JobStatus, Priority, UserRole

from app.models.job import Job
from app.repositories.job_repository import JobRepository
from app.repositories.skill_repository import SkillRepository
from app.schemas.job import (
    JobAssignedTechnicianSummary,
    JobCancelPayload,
    JobCreate,
    JobCreatorSummary,
    JobResponse,
    JobStatusPatch,
    JobUpdate,
    PaginatedJobResponse,
)
from app.schemas.skill import SkillResponse


class JobService:
    """Business service layer for job management operations."""

    def __init__(
        self,
        repository: JobRepository | None = None,
        skill_repo: SkillRepository | None = None,
    ) -> None:
        self.repo = repository or JobRepository()
        self.skill_repo = skill_repo or SkillRepository()

    def _to_response(self, job_obj: Job) -> JobResponse:
        """Convert Job ORM model to JobResponse DTO."""
        resp = JobResponse.model_validate(job_obj)
        resp.service_instructions = job_obj.description

        if job_obj.required_skill:
            resp.required_skill = SkillResponse.model_validate(job_obj.required_skill)

        if job_obj.creator:
            resp.creator = JobCreatorSummary.model_validate(job_obj.creator)

        if job_obj.assignments and len(job_obj.assignments) > 0:
            assigned = job_obj.assignments[0]
            if assigned.technician:
                full_n = (
                    assigned.technician.user.full_name
                    if assigned.technician.user
                    else "Assigned Tech"
                )
                resp.assigned_technician = JobAssignedTechnicianSummary(
                    id=assigned.technician.id,
                    employee_code=assigned.technician.employee_code,
                    full_name=full_n,
                )

        return resp

    async def list_jobs(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        required_skill_id: Optional[uuid.UUID] = None,
        scheduled_date: Optional[str] = None,
        assignment_status: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedJobResponse:
        """Query paginated jobs with search and filter parameters."""
        items, total = await self.repo.list_jobs(
            search=search,
            status=status,
            priority=priority,
            required_skill_id=required_skill_id,
            scheduled_date=scheduled_date,
            assignment_status=assignment_status,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1
        job_responses = [self._to_response(j) for j in items]

        return PaginatedJobResponse(
            items=job_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_my_jobs(self, user_id: uuid.UUID) -> list[JobResponse]:
        """Fetch jobs assigned to the current authenticated technician."""
        jobs = await self.repo.get_jobs_for_technician_user(user_id)
        return [self._to_response(j) for j in jobs]

    async def get_job_by_id(
        self,
        job_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        user_role: Optional[str] = None,
    ) -> JobResponse:
        """Fetch single job by UUID with role-based access checks for technicians."""
        job = await self.repo.get_by_id(job_id)
        if not job:
            raise NotFoundError("Job", str(job_id))

        if user_role == "Technician" and user_id is not None:
            is_assigned = await self.repo.is_technician_assigned_to_job(user_id, job_id)
            if not is_assigned:
                raise ForbiddenError("Technicians can only access jobs assigned to themselves.")

        return self._to_response(job)

    async def create_job(
        self,
        payload: JobCreate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> JobResponse:
        """Create new field service job."""
        # 1. Validate coordinates
        if not (-90.0 <= payload.latitude <= 90.0):
            raise BadRequestError(f"Invalid latitude {payload.latitude}. Must be between -90 and 90.")

        if not (-180.0 <= payload.longitude <= 180.0):
            raise BadRequestError(f"Invalid longitude {payload.longitude}. Must be between -180 and 180.")

        # 2. Validate required skill exists AND is ACTIVE
        skill = await self.skill_repo.get_by_id(payload.required_skill_id)
        if not skill:
            raise BadRequestError(f"Required skill ID '{payload.required_skill_id}' does not exist.")

        if skill.status != "ACTIVE":
            raise BadRequestError(f"Required skill '{skill.skill_name}' is currently INACTIVE and cannot be assigned to new jobs.")

        # 3. Generate server-side job number
        job_num = await self.repo.generate_next_job_number()

        # 4. Construct entity
        instructions = payload.service_instructions or payload.description
        job_obj = Job(
            id=uuid.uuid4(),
            job_number=job_num,
            customer_name=payload.customer_name.strip(),
            customer_phone=payload.customer_phone.strip() if payload.customer_phone else None,
            address=payload.address.strip(),
            latitude=payload.latitude,
            longitude=payload.longitude,
            required_skill_id=payload.required_skill_id,
            priority=payload.priority,
            status=JobStatus.NEW,
            scheduled_time=payload.scheduled_time,
            description=instructions.strip() if instructions else None,
            created_by=actor_id,
        )

        created = await self.repo.create_job(job_obj, actor_id=actor_id)
        full_job = await self.repo.get_by_id(created.id)
        return self._to_response(full_job or created)

    async def update_job(
        self,
        job_id: uuid.UUID,
        payload: JobUpdate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> JobResponse:
        """Update eligible details of an existing job."""
        job = await self.repo.get_by_id(job_id)
        if not job:
            raise NotFoundError("Job", str(job_id))

        if job.status == JobStatus.CANCELLED:
            raise BadRequestError("Cancelled jobs cannot be modified.")

        old_summary = f"Customer: {job.customer_name}, Priority: {job.priority}, SkillID: {job.required_skill_id}"

        # Validate coordinates if provided
        if payload.latitude is not None:
            if not (-90.0 <= payload.latitude <= 90.0):
                raise BadRequestError(f"Invalid latitude {payload.latitude}. Must be between -90 and 90.")
            job.latitude = payload.latitude

        if payload.longitude is not None:
            if not (-180.0 <= payload.longitude <= 180.0):
                raise BadRequestError(f"Invalid longitude {payload.longitude}. Must be between -180 and 180.")
            job.longitude = payload.longitude

        # Validate required skill if updated
        if payload.required_skill_id is not None and payload.required_skill_id != job.required_skill_id:
            skill = await self.skill_repo.get_by_id(payload.required_skill_id)
            if not skill:
                raise BadRequestError(f"Required skill ID '{payload.required_skill_id}' does not exist.")
            if skill.status != "ACTIVE":
                raise BadRequestError(f"Required skill '{skill.skill_name}' is currently INACTIVE.")
            job.required_skill_id = payload.required_skill_id

        if payload.customer_name is not None:
            job.customer_name = payload.customer_name.strip()

        if payload.customer_phone is not None:
            job.customer_phone = payload.customer_phone.strip() if payload.customer_phone else None

        if payload.address is not None:
            job.address = payload.address.strip()

        if payload.priority is not None:
            job.priority = payload.priority

        if payload.scheduled_time is not None:
            job.scheduled_time = payload.scheduled_time

        if payload.service_instructions is not None:
            job.description = payload.service_instructions.strip() if payload.service_instructions else None
        elif payload.description is not None:
            job.description = payload.description.strip() if payload.description else None

        new_summary = f"Customer: {job.customer_name}, Priority: {job.priority}, SkillID: {job.required_skill_id}"

        updated = await self.repo.update_job(job, old_summary, new_summary, actor_id=actor_id)
        full_job = await self.repo.get_by_id(updated.id)
        return self._to_response(full_job or updated)


    async def patch_status(
        self,
        job_id: uuid.UUID,
        payload: JobStatusPatch,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: Optional[str] = None,
    ) -> JobResponse:
        """Perform validated status transition on a job with RBAC and technician ownership checks."""
        job = await self.repo.get_by_id(job_id)
        if not job:
            raise NotFoundError("Job", str(job_id))

        old_status = str(job.status.value if hasattr(job.status, "value") else job.status)
        new_status = str(payload.status)

        if old_status == new_status:
            return self._to_response(job)

        # 1. Terminal state validations
        if old_status == JobStatus.COMPLETED.value:
            raise BadRequestError("Cannot change status of a COMPLETED job.")

        if old_status == JobStatus.CANCELLED.value:
            raise BadRequestError("Cannot change status of a CANCELLED job.")

        # 2. Forbidden target status via patch endpoint
        if new_status == JobStatus.CANCELLED.value:
            raise BadRequestError("Use the POST /jobs/{id}/cancel endpoint with a cancellation reason to cancel a job.")

        role_str = actor_role.value if hasattr(actor_role, "value") else str(actor_role) if actor_role else None

        # 3. RBAC & Technician Ownership Validation
        if role_str in (UserRole.ADMINISTRATOR.value, UserRole.DISPATCHER.value):
            raise ForbiddenError("Administrators and Dispatchers cannot perform technician execution status transitions.")

        if role_str == UserRole.TECHNICIAN.value:
            if not actor_id:
                raise ForbiddenError("Unauthenticated technician request.")
            is_assigned = await self.repo.is_technician_assigned_to_job(actor_id, job_id)
            if not is_assigned:
                raise ForbiddenError("You can only update execution status for jobs assigned to yourself.")



        # 4. Valid Transition Matrix Validation
        ALLOWED_TRANSITIONS: dict[str, list[str]] = {
            JobStatus.ASSIGNED.value: [JobStatus.TRAVELLING.value],
            JobStatus.TRAVELLING.value: [JobStatus.ARRIVED.value],
            JobStatus.ARRIVED.value: [JobStatus.WORKING.value],
            JobStatus.WORKING.value: [JobStatus.COMPLETED.value],
        }

        allowed_next = ALLOWED_TRANSITIONS.get(old_status, [])
        if new_status not in allowed_next:
            raise BadRequestError(
                f"Invalid status transition from '{old_status}' to '{new_status}'. Allowed next status: {allowed_next}"
            )

        updated = await self.repo.update_status(job, old_status, new_status, actor_id=actor_id)
        full_job = await self.repo.get_by_id(updated.id)
        return self._to_response(full_job or updated)


    async def cancel_job(
        self,
        job_id: uuid.UUID,
        payload: JobCancelPayload,
        actor_id: Optional[uuid.UUID] = None,
    ) -> JobResponse:
        """Cancel a job with controlled state transition and reason."""
        job = await self.repo.get_by_id(job_id)
        if not job:
            raise NotFoundError("Job", str(job_id))

        if job.status == JobStatus.CANCELLED:
            return self._to_response(job)

        if not payload.reason or not payload.reason.strip():
            raise BadRequestError("A non-empty cancellation reason is required.")

        cancelled = await self.repo.cancel_job(job, payload.reason.strip(), actor_id=actor_id)
        full_job = await self.repo.get_by_id(cancelled.id)
        return self._to_response(full_job or cancelled)
