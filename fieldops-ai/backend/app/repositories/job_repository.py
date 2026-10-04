"""
Job Repository Layer providing data access, filtering, server-side job_number generation, and audit logging.
"""

from datetime import datetime, timezone
import math
from typing import Optional
import uuid

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import AsyncSessionLocal
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.enums import JobStatus, Priority
from app.models.job import Job
from app.models.technician import Technician


class JobRepository:
    """Data access layer for Job entities."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def generate_next_job_number(self) -> str:
        """Generates server-side unique sequential job number (e.g. JOB-10001)."""
        async def _execute(db: AsyncSession):
            stmt = select(func.count(Job.id))
            count = (await db.execute(stmt)).scalar() or 0
            candidate_num = count + 10001
            job_num = f"JOB-{candidate_num}"

            # Verify uniqueness
            chk_stmt = select(Job).where(Job.job_number == job_num)
            res = await db.execute(chk_stmt)
            if res.scalar_one_or_none():
                # fallback with random suffix if collision
                job_num = f"JOB-{candidate_num}-{str(uuid.uuid4())[:4].upper()}"
            return job_num

        if self.session:
            return await _execute(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)

    async def get_by_id(self, job_id: uuid.UUID) -> Optional[Job]:
        """Fetch job by UUID with eager loaded relationships."""
        stmt = (
            select(Job)
            .options(
                selectinload(Job.required_skill),
                selectinload(Job.creator),
                selectinload(Job.assignments).selectinload(Assignment.technician).selectinload(Technician.user),
            )
            .where(Job.id == job_id)
        )
        if self.session:
            res = await self.session.execute(stmt)
            return res.scalar_one_or_none()

        async with AsyncSessionLocal() as db:
            res = await db.execute(stmt)
            return res.scalar_one_or_none()

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
    ) -> tuple[list[Job], int]:
        """Paginated, filtered, and sorted jobs query."""
        async def _execute(db: AsyncSession):
            query = select(Job).options(
                selectinload(Job.required_skill),
                selectinload(Job.creator),
                selectinload(Job.assignments).selectinload(Assignment.technician).selectinload(Technician.user),
            )

            filters = []
            if search and search.strip():
                s = f"%{search.strip()}%"
                filters.append(
                    or_(
                        Job.job_number.ilike(s),
                        Job.customer_name.ilike(s),
                        Job.address.ilike(s),
                        Job.description.ilike(s),
                    )
                )

            if status and status.strip() and status.upper() != "ALL":
                filters.append(Job.status == status.strip().upper())

            if priority and priority.strip() and priority.upper() != "ALL":
                filters.append(Job.priority == priority.strip().upper())

            if required_skill_id:
                filters.append(Job.required_skill_id == required_skill_id)

            if scheduled_date and scheduled_date.strip():
                try:
                    target_d = datetime.strptime(scheduled_date.strip(), "%Y-%m-%d").date()
                    filters.append(cast(Job.scheduled_time, Date) == target_d)
                except ValueError:
                    pass

            if assignment_status and assignment_status.strip() and assignment_status.upper() != "ALL":
                asg_val = assignment_status.strip().upper()
                if asg_val == "UNASSIGNED":
                    filters.append(Job.status == JobStatus.NEW)
                elif asg_val == "ASSIGNED":
                    filters.append(Job.status != JobStatus.NEW)

            if filters:
                query = query.where(*filters)

            # Count total
            count_query = select(func.count(Job.id))
            if filters:
                count_query = count_query.where(*filters)
            total = (await db.execute(count_query)).scalar() or 0

            # Sorting
            sort_attr = getattr(Job, sort_by, Job.created_at)
            if sort_order.lower() == "asc":
                query = query.order_by(sort_attr.asc())
            else:
                query = query.order_by(sort_attr.desc())

            offset = (max(page, 1) - 1) * page_size
            query = query.offset(offset).limit(page_size)

            res = await db.execute(query)
            items = list(res.scalars().all())

            return items, total

        if self.session:
            return await _execute(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)

    async def get_jobs_for_technician_user(self, user_id: uuid.UUID) -> list[Job]:
        """Fetch jobs assigned to a specific user's technician profile."""
        async def _execute(db: AsyncSession):
            # First find technician.id from user_id
            tech_stmt = select(Technician.id).where(Technician.user_id == user_id)
            tech_res = await db.execute(tech_stmt)
            tech_id = tech_res.scalar_one_or_none()

            if not tech_id:
                return []

            stmt = (
                select(Job)
                .join(Assignment, Assignment.job_id == Job.id)
                .options(
                    selectinload(Job.required_skill),
                    selectinload(Job.creator),
                    selectinload(Job.assignments).selectinload(Assignment.technician).selectinload(Technician.user),
                )
                .where(Assignment.technician_id == tech_id)
                .order_by(Job.scheduled_time.asc().nulls_last())
            )
            res = await db.execute(stmt)
            return list(res.scalars().all())

        if self.session:
            return await _execute(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)

    async def is_technician_assigned_to_job(self, user_id: uuid.UUID | str, job_id: uuid.UUID | str) -> bool:
        """Check if user_id's technician profile is assigned to job_id."""
        u_uuid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        j_uuid = uuid.UUID(str(job_id)) if not isinstance(job_id, uuid.UUID) else job_id

        async def _execute(db: AsyncSession):
            tech_stmt = select(Technician.id).where(Technician.user_id == u_uuid)
            tech_res = await db.execute(tech_stmt)
            tech_id = tech_res.scalar_one_or_none()
            if not tech_id:
                return False

            asg_stmt = (
                select(Assignment.id)
                .where(
                    Assignment.job_id == j_uuid,
                    Assignment.technician_id == tech_id,
                    Assignment.assignment_status != "UNASSIGNED",
                )
            )
            asg_res = await db.execute(asg_stmt)
            return asg_res.scalar_one_or_none() is not None

        if self.session:
            return await _execute(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)



    async def create_job(
        self,
        job_obj: Job,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Job:
        """Create new Job entity and write AuditLog."""
        async def _execute_create(db: AsyncSession):
            db.add(job_obj)
            await db.flush()

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="JOB_CREATED",
                entity="Job",
                entity_id=str(job_obj.id),
                reason=f"Created job {job_obj.job_number} for customer {job_obj.customer_name}",
                new_value=f"JobNumber: {job_obj.job_number}, Customer: {job_obj.customer_name}, Priority: {job_obj.priority}, Status: {job_obj.status}",
            )
            db.add(audit)
            await db.commit()
            return job_obj

        if self.session:
            return await _execute_create(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_create(db_session)

    async def update_job(
        self,
        job_obj: Job,
        old_summary: str,
        new_summary: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Job:
        """Update existing Job entity and write AuditLog."""
        async def _execute_update(db: AsyncSession):
            db.add(job_obj)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="JOB_UPDATED",
                entity="Job",
                entity_id=str(job_obj.id),
                reason=f"Updated job {job_obj.job_number}",
                old_value=old_summary,
                new_value=new_summary,
            )
            db.add(audit)
            await db.commit()
            return job_obj

        if self.session:
            return await _execute_update(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_update(db_session)

    async def update_status(
        self,
        job_obj: Job,
        old_status: str,
        new_status: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Job:
        """Update job status, synchronize technician availability on completion, and write AuditLog."""
        async def _execute_status(db: AsyncSession):
            job_obj.status = JobStatus(new_status)
            db.add(job_obj)

            # If job completed, set assigned technician's availability back to AVAILABLE
            if new_status == JobStatus.COMPLETED.value or new_status == "COMPLETED":
                asg_stmt = (
                    select(Assignment)
                    .options(selectinload(Assignment.technician))
                    .where(
                        Assignment.job_id == job_obj.id,
                        Assignment.assignment_status != "UNASSIGNED",
                    )
                )
                asg_res = await db.execute(asg_stmt)
                active_asg = asg_res.scalar_one_or_none()
                if active_asg and active_asg.technician:
                    tech = active_asg.technician
                    tech.availability_status = "AVAILABLE"
                    db.add(tech)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="JOB_STATUS_CHANGED",
                entity="Job",
                entity_id=str(job_obj.id),
                reason=f"Job {job_obj.job_number} status changed from {old_status} to {new_status}",
                old_value=f"status={old_status}",
                new_value=f"status={new_status}",
            )
            db.add(audit)
            await db.commit()
            return job_obj

        if self.session:
            return await _execute_status(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_status(db_session)

    async def cancel_job(
        self,
        job_obj: Job,
        reason: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Job:
        """Cancel job, unassign active assignments, restore technician availability, and write AuditLog."""
        async def _execute_cancel(db: AsyncSession):
            old_status = str(job_obj.status)
            job_obj.status = JobStatus.CANCELLED
            db.add(job_obj)

            # Revert any active assignment for this job and restore technician availability
            asg_stmt = (
                select(Assignment)
                .options(selectinload(Assignment.technician))
                .where(
                    Assignment.job_id == job_obj.id,
                    Assignment.assignment_status != "UNASSIGNED",
                )
            )
            asg_res = await db.execute(asg_stmt)
            active_asgs = asg_res.scalars().all()
            for asg in active_asgs:
                asg.assignment_status = "UNASSIGNED"
                db.add(asg)
                if asg.technician:
                    asg.technician.availability_status = "AVAILABLE"
                    db.add(asg.technician)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="JOB_CANCELLED",
                entity="Job",
                entity_id=str(job_obj.id),
                reason=f"Cancelled job {job_obj.job_number}. Reason: {reason}",
                old_value=f"status={old_status}",
                new_value=f"status=CANCELLED, reason={reason}",
            )
            db.add(audit)
            await db.commit()
            return job_obj

        if self.session:
            return await _execute_cancel(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_cancel(db_session)
