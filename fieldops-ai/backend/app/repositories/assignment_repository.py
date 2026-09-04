"""
Assignment Repository for managing assignment database queries, transactions, and audit logging.
"""

from datetime import datetime, timezone
import json
from typing import Optional
import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import AsyncSessionLocal
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.enums import AssignmentType, JobStatus
from app.models.job import Job
from app.models.technician import Technician


class AssignmentRepository:
    """Repository pattern implementation for Assignment entity persistence."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def get_job_by_id(self, job_id: uuid.UUID) -> Optional[Job]:
        """Fetch job with required skill loaded."""
        async def _execute(db: AsyncSession):
            stmt = (
                select(Job)
                .options(selectinload(Job.required_skill))
                .where(Job.id == job_id)
            )
            res = await db.execute(stmt)
            return res.scalar_one_or_none()

        if self.session:
            return await _execute(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)

    async def get_all_technicians(self) -> list[Technician]:
        """Fetch all technicians with user, primary_skill, and active assignments loaded."""
        async def _execute(db: AsyncSession):
            stmt = (
                select(Technician)
                .options(
                    selectinload(Technician.user),
                    selectinload(Technician.primary_skill),
                    selectinload(Technician.assignments),
                )
            )
            res = await db.execute(stmt)
            return list(res.scalars().all())

        if self.session:
            return await _execute(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)

    async def get_technician_by_id(self, technician_id: uuid.UUID) -> Optional[Technician]:
        """Fetch single technician by ID with user loaded."""
        async def _execute(db: AsyncSession):
            stmt = (
                select(Technician)
                .options(
                    selectinload(Technician.user),
                    selectinload(Technician.primary_skill),
                )
                .where(Technician.id == technician_id)
            )
            res = await db.execute(stmt)
            return res.scalar_one_or_none()

        if self.session:
            return await _execute(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)

    async def get_active_assignment_for_job(self, job_id: uuid.UUID) -> Optional[Assignment]:
        """Fetch active assignment for job if exists."""
        async def _execute(db: AsyncSession):
            stmt = (
                select(Assignment)
                .options(
                    selectinload(Assignment.technician).selectinload(Technician.user),
                    selectinload(Assignment.job),
                )
                .where(
                    and_(
                        Assignment.job_id == job_id,
                        Assignment.assignment_status == "ASSIGNED",
                    )
                )
            )
            res = await db.execute(stmt)
            return res.scalar_one_or_none()

        if self.session:
            return await _execute(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)

    async def create_assignment_transaction(
        self,
        job_id: uuid.UUID,
        technician_id: uuid.UUID,
        assigned_by_user_id: uuid.UUID,
        assignment_type: AssignmentType = AssignmentType.SYSTEM,
    ) -> Assignment:
        """Atomically creates assignment, updates job status to ASSIGNED, and records audit event."""
        async def _execute(db: AsyncSession):
            job_stmt = select(Job).where(Job.id == job_id).with_for_update()
            job_res = await db.execute(job_stmt)
            job = job_res.scalar_one_or_none()
            if not job:
                raise ValueError("Job not found.")

            if job.status == JobStatus.CANCELLED:
                raise ValueError("Cannot assign a cancelled job.")
            if job.status == JobStatus.ASSIGNED:
                raise ValueError("Job is already assigned to a technician.")

            assignment = Assignment(
                id=uuid.uuid4(),
                job_id=job_id,
                technician_id=technician_id,
                assigned_by=assigned_by_user_id,
                assignment_type=assignment_type,
                assignment_status="ASSIGNED",
                assigned_at=datetime.now(timezone.utc),
            )
            db.add(assignment)

            old_status = job.status.value
            job.status = JobStatus.ASSIGNED
            job.updated_at = datetime.now(timezone.utc)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=assigned_by_user_id,
                action="TECHNICIAN_ASSIGNED",
                entity="Job",
                entity_id=str(job_id),
                old_value=json.dumps({"status": old_status, "technician_id": None}),
                new_value=json.dumps({
                    "status": JobStatus.ASSIGNED.value,
                    "technician_id": str(technician_id),
                    "job_id": str(job_id),
                    "job_number": job.job_number,
                    "assigned_at": datetime.now(timezone.utc).isoformat(),
                }),
                reason=f"Assigned technician {technician_id} via {assignment_type.value} dispatch",
            )
            db.add(audit)

            await db.commit()
            await db.refresh(assignment)
            return assignment

        if self.session:
            return await _execute(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)

    async def unassign_job_transaction(
        self,
        job_id: uuid.UUID,
        unassigned_by_user_id: uuid.UUID,
        reason: str = "Dispatcher unassigned job",
    ) -> Job:
        """Atomically marks current assignment UNASSIGNED, reverts job status to NEW, and logs audit."""
        async def _execute(db: AsyncSession):
            job_stmt = select(Job).where(Job.id == job_id).with_for_update()
            job_res = await db.execute(job_stmt)
            job = job_res.scalar_one_or_none()
            if not job:
                raise ValueError("Job not found.")

            asg_stmt = (
                select(Assignment)
                .where(
                    and_(
                        Assignment.job_id == job_id,
                        Assignment.assignment_status == "ASSIGNED",
                    )
                )
                .with_for_update()
            )
            asg_res = await db.execute(asg_stmt)
            assignment = asg_res.scalar_one_or_none()

            if not assignment and job.status != JobStatus.ASSIGNED:
                raise ValueError("Job is not currently assigned.")

            old_tech_id = str(assignment.technician_id) if assignment else None
            if assignment:
                assignment.assignment_status = "UNASSIGNED"

            old_status = job.status.value
            job.status = JobStatus.NEW
            job.updated_at = datetime.now(timezone.utc)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=unassigned_by_user_id,
                action="JOB_UNASSIGNED",
                entity="Job",
                entity_id=str(job_id),
                old_value=json.dumps({"status": old_status, "technician_id": old_tech_id}),
                new_value=json.dumps({"status": JobStatus.NEW.value, "technician_id": None}),
                reason=reason,
            )
            db.add(audit)

            await db.commit()
            await db.refresh(job)
            return job

        if self.session:
            return await _execute(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)

    async def log_audit_event(
        self,
        actor_id: uuid.UUID,
        action: str,
        entity_id: str,
        old_value: dict | None = None,
        new_value: dict | None = None,
        reason: str | None = None,
    ) -> None:
        """Log audit event helper."""
        async def _execute(db: AsyncSession):
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action=action,
                entity="Assignment",
                entity_id=entity_id,
                old_value=json.dumps(old_value) if old_value else None,
                new_value=json.dumps(new_value) if new_value else None,
                reason=reason,
            )
            db.add(audit)
            await db.commit()

        if self.session:
            await _execute(self.session)
        else:
            async with AsyncSessionLocal() as db_session:
                await _execute(db_session)
