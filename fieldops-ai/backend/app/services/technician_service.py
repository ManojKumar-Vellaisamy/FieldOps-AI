"""
Technician Service Layer managing business workflows, validations, and transaction orchestration.
"""

from datetime import datetime, timedelta, timezone
import math
from typing import Optional
import uuid

from sqlalchemy import select
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import get_password_hash
from app.database.session import AsyncSessionLocal
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.enums import JobStatus, UserRole, UserStatus
from app.models.job import Job
from app.models.technician import Technician
from app.models.user import User
from app.repositories.technician_repository import TechnicianRepository
from app.schemas.technician import (
    PaginatedTechnicianResponse,
    SkillSummary,
    TechnicianCreate,
    TechnicianResponse,
    TechnicianSkillsResponse,
    TechnicianStatusPatch,
    TechnicianUpdate,
)
from app.services.settings_service import SettingsService
from app.core.realtime import (
    ws_manager,
    EVENT_TECHNICIAN_LOCATION_UPDATED,
    EVENT_TECHNICIAN_AVAILABILITY_CHANGED,
    EVENT_ETA_UPDATED,
)


class TechnicianService:
    """Business service layer for technician management operations."""


    def __init__(self, repository: TechnicianRepository | None = None) -> None:
        self.repo = repository or TechnicianRepository()

    async def list_technicians(
        self,
        search: Optional[str] = None,
        availability_status: Optional[str] = None,
        skill_id: Optional[uuid.UUID] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedTechnicianResponse:
        """Query paginated technicians with filtering and sorting."""
        items, total = await self.repo.list_technicians(
            search=search,
            availability_status=availability_status,
            skill_id=skill_id,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return PaginatedTechnicianResponse(
            items=[TechnicianResponse.model_validate(tech) for tech in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_technician_by_id(self, tech_id: uuid.UUID) -> TechnicianResponse:
        """Fetch technician profile by UUID."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))
        return TechnicianResponse.model_validate(tech)

    async def create_technician(
        self,
        payload: TechnicianCreate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TechnicianResponse:
        """Create new technician profile and user account."""
        # 1. Validate employee code uniqueness
        existing_code = await self.repo.get_by_employee_code(payload.employee_code)
        if existing_code:
            raise ConflictError(f"Employee code '{payload.employee_code}' already exists.")

        # 2. Validate required primary skill
        skill = await self.repo.get_skill_by_id(payload.primary_skill_id)
        if not skill:
            raise ValidationError(f"Primary skill with ID '{payload.primary_skill_id}' does not exist.")

        # 3. Fetch Technician security role
        role = await self.repo.get_role_by_name(UserRole.TECHNICIAN.value)
        if not role:
            raise ValidationError("Technician security role is missing in system configuration.")

        # 4. Check email: attach to existing user without profile, or create new user
        existing_user = await self.repo.get_user_by_email(payload.email)
        if existing_user:
            existing_tech = await self.repo.get_by_user_id(existing_user.id)
            if existing_tech:
                raise ConflictError(f"Technician profile already exists for user '{payload.email}'.")
            user_obj = existing_user
            user_obj.full_name = payload.full_name.strip()
            if payload.phone:
                user_obj.phone = payload.phone.strip()
            if payload.password:
                user_obj.password_hash = get_password_hash(payload.password)
            user_obj.role_id = role.id
            user_obj.must_change_password = True
        else:
            user_obj = User(
                id=uuid.uuid4(),
                role_id=role.id,
                email=payload.email.strip().lower(),
                full_name=payload.full_name.strip(),
                password_hash=get_password_hash(payload.password),
                phone=payload.phone.strip() if payload.phone else None,
                status=UserStatus.ACTIVE,
                must_change_password=True,
            )

        # 5. Build technician entity
        tech_obj = Technician(
            id=uuid.uuid4(),
            employee_code=payload.employee_code.strip().upper(),
            primary_skill_id=payload.primary_skill_id,
            years_experience=payload.years_experience,
            availability_status=payload.availability_status.strip().upper(),
            current_latitude=payload.current_latitude,
            current_longitude=payload.current_longitude,
        )

        created_tech = await self.repo.create_technician_with_user(user_obj, tech_obj, actor_id=actor_id)
        return TechnicianResponse.model_validate(created_tech)

    async def update_technician(
        self,
        tech_id: uuid.UUID,
        payload: TechnicianUpdate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TechnicianResponse:
        """Update existing technician profile details."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        user_obj = tech.user
        if not user_obj:
            raise NotFoundError("User", str(tech.user_id))

        old_summary = f"Name: {user_obj.full_name}, Email: {user_obj.email}, Phone: {user_obj.phone}, Exp: {tech.years_experience}, Status: {tech.availability_status}"

        if payload.email and payload.email.strip().lower() != user_obj.email.lower():
            existing_email = await self.repo.get_user_by_email(payload.email)
            if existing_email:
                raise ConflictError(f"User email '{payload.email}' already exists.")
            user_obj.email = payload.email.strip().lower()

        if payload.full_name is not None:
            user_obj.full_name = payload.full_name.strip()

        if payload.phone is not None:
            user_obj.phone = payload.phone.strip() if payload.phone else None

        if payload.primary_skill_id is not None:
            skill = await self.repo.get_skill_by_id(payload.primary_skill_id)
            if not skill:
                raise ValidationError(f"Skill with ID '{payload.primary_skill_id}' does not exist.")
            tech.primary_skill_id = payload.primary_skill_id

        if payload.years_experience is not None:
            tech.years_experience = payload.years_experience

        if payload.availability_status is not None:
            tech.availability_status = payload.availability_status.strip().upper()

        if "current_latitude" in payload.model_fields_set:
            tech.current_latitude = payload.current_latitude

        if "current_longitude" in payload.model_fields_set:
            tech.current_longitude = payload.current_longitude

        new_summary = f"Name: {user_obj.full_name}, Email: {user_obj.email}, Phone: {user_obj.phone}, Exp: {tech.years_experience}, Status: {tech.availability_status}"

        updated_tech = await self.repo.update_technician_with_user(
            tech, user_obj, old_summary, new_summary, actor_id=actor_id
        )
        if tech.availability_status == "INACTIVE":
            await self._auto_unassign_if_needed(tech.id, "INACTIVE", actor_id=actor_id)

        return TechnicianResponse.model_validate(updated_tech)

    async def patch_status(
        self,
        tech_id: uuid.UUID,
        payload: TechnicianStatusPatch,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TechnicianResponse:
        """Update technician availability status."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        old_status = tech.availability_status
        new_status = payload.availability_status.strip().upper()

        updated_tech = await self.repo.update_status(tech, old_status, new_status, actor_id=actor_id)
        if new_status == "INACTIVE":
            await self._auto_unassign_if_needed(tech.id, new_status, actor_id=actor_id)

        # Broadcast availability status update
        await ws_manager.broadcast_operational_event(
            EVENT_TECHNICIAN_AVAILABILITY_CHANGED,
            {
                "technician_id": str(updated_tech.id),
                "user_id": str(updated_tech.user_id),
                "employee_code": updated_tech.employee_code,
                "full_name": updated_tech.user.full_name if updated_tech.user else "",
                "old_status": old_status,
                "new_status": new_status,
                "updated_at": updated_tech.updated_at.isoformat() if updated_tech.updated_at else None,
            },
            technician_user_id=updated_tech.user_id,
        )

        return TechnicianResponse.model_validate(updated_tech)

    async def update_location(
        self,
        tech_id: uuid.UUID,
        latitude: float,
        longitude: float,
        recorded_at: Optional[datetime] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TechnicianResponse:
        """Update technician GPS location telemetry."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        if not (-90.0 <= latitude <= 90.0):
            raise ValidationError(f"Invalid latitude {latitude}. Must be between -90 and 90.")

        if not (-180.0 <= longitude <= 180.0):
            raise ValidationError(f"Invalid longitude {longitude}. Must be between -180 and 180.")

        if recorded_at is not None:
            if recorded_at.tzinfo is None:
                recorded_at = recorded_at.replace(tzinfo=timezone.utc)
            else:
                recorded_at = recorded_at.astimezone(timezone.utc)
            now = datetime.now(timezone.utc)
            if recorded_at > now + timedelta(seconds=300):
                raise ValidationError("recorded_at timestamp cannot be in the future (max 300s clock drift allowed).")

        updated_tech = await self.repo.update_location(
            tech, latitude, longitude, recorded_at=recorded_at, actor_id=actor_id
        )

        # Broadcast live GPS telemetry update to dispatchers and technician
        await ws_manager.broadcast_operational_event(
            EVENT_TECHNICIAN_LOCATION_UPDATED,
            {
                "technician_id": str(updated_tech.id),
                "user_id": str(updated_tech.user_id),
                "employee_code": updated_tech.employee_code,
                "full_name": updated_tech.user.full_name if updated_tech.user else "",
                "latitude": latitude,
                "longitude": longitude,
                "location_updated_at": updated_tech.location_updated_at.isoformat() if updated_tech.location_updated_at else None,
                "updated_at": updated_tech.updated_at.isoformat() if updated_tech.updated_at else None,
            },
            technician_user_id=updated_tech.user_id,
        )

        # Trigger authoritative ETA recalculation for active assigned jobs
        await self._recalculate_active_jobs_eta(updated_tech.id)

        return TechnicianResponse.model_validate(updated_tech)

    async def _recalculate_active_jobs_eta(self, tech_id: uuid.UUID) -> None:
        """Find active assigned jobs for this technician and trigger authoritative ETA recalculation."""
        from app.services.eta_service import ETAService

        # Fetch technician user_id so ETA_UPDATED is routed to the technician's WebSocket
        tech_user_id: uuid.UUID | None = None
        async with AsyncSessionLocal() as session:
            stmt_tech = select(Technician).where(Technician.id == tech_id)
            res_tech = await session.execute(stmt_tech)
            tech_obj = res_tech.scalar_one_or_none()
            if tech_obj:
                tech_user_id = tech_obj.user_id

        job_ids = []
        async with AsyncSessionLocal() as session:
            stmt = select(Assignment.job_id).where(
                Assignment.technician_id == tech_id,
                Assignment.assignment_status.in_(["ASSIGNED", "TRAVELLING", "ARRIVED", "WORKING"]),
            )
            res = await session.execute(stmt)
            job_ids = list(res.scalars().all())

        if not job_ids:
            return

        eta_service = ETAService()
        for j_id in job_ids:
            try:
                eta_resp = await eta_service.calculate_job_eta(job_id=j_id, technician_id=tech_id)
                eta_dict = eta_resp.model_dump(mode="json")
                eta_dict["job_id"] = str(j_id)
                eta_dict["updated_at"] = eta_resp.calculated_at.isoformat() if eta_resp.calculated_at else None
                await ws_manager.broadcast_operational_event(
                    EVENT_ETA_UPDATED,
                    eta_dict,
                    technician_user_id=tech_user_id,
                )
            except Exception as e:
                logger.warning("recalculate_active_jobs_eta_failed", job_id=str(j_id), error=str(e))


    async def activate_technician(
        self,
        tech_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TechnicianResponse:
        """Activate an inactive technician and restore operational availability."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        updated_tech = await self.repo.activate_technician(tech_id, actor_id=actor_id)
        if not updated_tech:
            raise NotFoundError("Technician", str(tech_id))

        # Broadcast status update event
        await ws_manager.broadcast_operational_event(
            EVENT_TECHNICIAN_AVAILABILITY_CHANGED,
            {
                "technician_id": str(updated_tech.id),
                "user_id": str(updated_tech.user_id),
                "employee_code": updated_tech.employee_code,
                "full_name": updated_tech.user.full_name if updated_tech.user else "",
                "old_status": tech.availability_status,
                "new_status": "AVAILABLE",
                "updated_at": updated_tech.updated_at.isoformat() if updated_tech.updated_at else None,
            },
            technician_user_id=updated_tech.user_id,
        )

        return TechnicianResponse.model_validate(updated_tech)

    async def deactivate_technician(
        self,
        tech_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TechnicianResponse:
        """Deactivate technician profile and auto-unassign active jobs if configured."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        old_status = tech.availability_status
        updated_tech = await self.repo.deactivate_technician(tech_id, actor_id=actor_id)
        if not updated_tech:
            raise NotFoundError("Technician", str(tech_id))

        await self._auto_unassign_if_needed(tech_id, "INACTIVE", actor_id=actor_id)

        # Broadcast status update event
        await ws_manager.broadcast_operational_event(
            EVENT_TECHNICIAN_AVAILABILITY_CHANGED,
            {
                "technician_id": str(updated_tech.id),
                "user_id": str(updated_tech.user_id),
                "employee_code": updated_tech.employee_code,
                "full_name": updated_tech.user.full_name if updated_tech.user else "",
                "old_status": old_status,
                "new_status": "INACTIVE",
                "updated_at": updated_tech.updated_at.isoformat() if updated_tech.updated_at else None,
            },
            technician_user_id=updated_tech.user_id,
        )

        return TechnicianResponse.model_validate(updated_tech)

    async def reset_password(
        self,
        tech_id: uuid.UUID,
        new_password: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TechnicianResponse:
        """Reset technician user password to a new temporary password."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        new_hash = get_password_hash(new_password)
        updated_tech = await self.repo.reset_technician_password(tech_id, new_hash, actor_id=actor_id)
        if not updated_tech:
            raise NotFoundError("Technician", str(tech_id))

        return TechnicianResponse.model_validate(updated_tech)

    async def check_dependencies(self, tech_id: uuid.UUID) -> dict:
        """Inspect technician operational dependencies before deletion."""
        return await self.repo.check_dependencies(tech_id)

    async def delete_technician(
        self,
        tech_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """Safely permanently delete technician with zero operational dependencies."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        return await self.repo.permanent_delete_technician(tech_id, actor_id=actor_id)


    async def _auto_unassign_if_needed(
        self,
        tech_id: uuid.UUID,
        new_status: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Auto-unassign active jobs if technician profile becomes INACTIVE and setting is enabled."""
        if new_status.upper() != "INACTIVE":
            return

        sys_settings = await SettingsService().get_settings()
        if not sys_settings.auto_unassign_on_tech_inactive:
            return

        async with AsyncSessionLocal() as session:
            stmt = select(Assignment).where(
                Assignment.technician_id == tech_id,
                Assignment.assignment_status.in_(["ASSIGNED", "TRAVELLING", "ARRIVED", "WORKING"]),
            )
            res = await session.execute(stmt)
            assignments = list(res.scalars().all())

            for asg in assignments:
                asg.assignment_status = "CANCELLED"
                session.add(asg)

                job_stmt = select(Job).where(Job.id == asg.job_id)
                job_res = await session.execute(job_stmt)
                job = job_res.scalar_one_or_none()

                if job and job.status not in (JobStatus.COMPLETED, JobStatus.CANCELLED):
                    job.status = JobStatus.NEW
                    session.add(job)

                audit = AuditLog(
                    id=uuid.uuid4(),
                    user_id=actor_id,
                    action="JOB_UNASSIGNED_TECH_INACTIVE",
                    entity="Job",
                    entity_id=str(asg.job_id),
                    reason="Auto-unassigned active job because technician availability status set to INACTIVE",
                    old_value=f"technician_id={tech_id}, status={asg.assignment_status}",
                    new_value="assignment_status=CANCELLED, job_status=NEW",
                )
                session.add(audit)

            if assignments:
                await session.commit()


    async def get_technician_skills(self, tech_id: uuid.UUID) -> TechnicianSkillsResponse:
        """Fetch technician primary and secondary skill associations."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        primary = SkillSummary.model_validate(tech.primary_skill) if tech.primary_skill else None
        skills = [primary] if primary else []

        return TechnicianSkillsResponse(
            technician_id=tech.id,
            employee_code=tech.employee_code,
            primary_skill=primary,
            skills=skills,
        )

