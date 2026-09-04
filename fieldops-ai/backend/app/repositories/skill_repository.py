"""
Skill Repository Layer providing data access, filtering, pagination, and audit logging.
"""

from datetime import datetime, timezone
import math
from typing import Optional
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.skill import Skill
from app.models.technician import Technician
from app.models.user import User


class SkillRepository:
    """Data access layer for Skill entities."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def get_by_id(self, skill_id: uuid.UUID) -> Optional[Skill]:
        """Fetch skill by UUID."""
        stmt = select(Skill).where(Skill.id == skill_id)
        if self.session:
            res = await self.session.execute(stmt)
            return res.scalar_one_or_none()

        async with AsyncSessionLocal() as db:
            res = await db.execute(stmt)
            return res.scalar_one_or_none()

    async def get_by_name(self, skill_name: str) -> Optional[Skill]:
        """Case-insensitive query by skill_name."""
        clean_name = skill_name.strip().lower()
        stmt = select(Skill).where(func.lower(Skill.skill_name) == clean_name)
        if self.session:
            res = await self.session.execute(stmt)
            return res.scalar_one_or_none()

        async with AsyncSessionLocal() as db:
            res = await db.execute(stmt)
            return res.scalar_one_or_none()

    async def list_skills(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[tuple[Skill, int]], int, int, int]:
        """
        Paginated, filtered, and sorted skills query.
        Returns ((Skill, technician_count)[], total, total_active, total_inactive).
        """
        async def _execute(db: AsyncSession):
            # Subquery to count technicians per primary skill
            tech_count_sub = (
                select(Technician.primary_skill_id, func.count(Technician.id).label("t_count"))
                .group_by(Technician.primary_skill_id)
                .subquery()
            )

            query = (
                select(Skill, func.coalesce(tech_count_sub.c.t_count, 0).label("tech_count"))
                .outerjoin(tech_count_sub, Skill.id == tech_count_sub.c.primary_skill_id)
            )

            filters = []
            if search and search.strip():
                s = f"%{search.strip()}%"
                filters.append(or_(Skill.skill_name.ilike(s), Skill.description.ilike(s)))

            if category and category.strip() and category.upper() != "ALL":
                filters.append(Skill.category.ilike(category.strip()))

            if status and status.strip() and status.upper() != "ALL":
                filters.append(Skill.status == status.strip().upper())

            if filters:
                query = query.where(*filters)

            # Count total
            count_query = select(func.count(Skill.id))
            if filters:
                count_query = count_query.where(*filters)
            total = (await db.execute(count_query)).scalar() or 0

            # Count totals by status
            active_count = (await db.execute(select(func.count(Skill.id)).where(Skill.status == "ACTIVE"))).scalar() or 0
            inactive_count = (await db.execute(select(func.count(Skill.id)).where(Skill.status == "INACTIVE"))).scalar() or 0

            # Sorting
            sort_attr = getattr(Skill, sort_by, Skill.created_at)
            if sort_order.lower() == "asc":
                query = query.order_by(sort_attr.asc())
            else:
                query = query.order_by(sort_attr.desc())

            offset = (max(page, 1) - 1) * page_size
            query = query.offset(offset).limit(page_size)

            res = await db.execute(query)
            rows = res.all()
            items = [(row[0], int(row[1])) for row in rows]

            return items, total, active_count, inactive_count

        if self.session:
            return await _execute(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute(db_session)

    async def get_technician_count_for_skill(self, skill_id: uuid.UUID) -> int:
        """Get count of technicians associated with a skill."""
        stmt = select(func.count(Technician.id)).where(Technician.primary_skill_id == skill_id)
        if self.session:
            res = await self.session.execute(stmt)
            return res.scalar() or 0

        async with AsyncSessionLocal() as db:
            res = await db.execute(stmt)
            return res.scalar() or 0

    async def get_technicians_by_skill(self, skill_id: uuid.UUID) -> list[Technician]:
        """Fetch all technicians associated with a specific primary skill."""
        stmt = (
            select(Technician)
            .options(selectinload(Technician.user))
            .where(Technician.primary_skill_id == skill_id)
        )
        if self.session:
            res = await self.session.execute(stmt)
            return list(res.scalars().all())

        async with AsyncSessionLocal() as db:
            res = await db.execute(stmt)
            return list(res.scalars().all())

    async def get_skills_for_technician_user(self, user_id: uuid.UUID) -> list[Skill]:
        """Fetch skills associated with a specific user's technician profile."""
        stmt = (
            select(Skill)
            .join(Technician, Technician.primary_skill_id == Skill.id)
            .where(Technician.user_id == user_id)
        )
        if self.session:
            res = await self.session.execute(stmt)
            return list(res.scalars().all())

        async with AsyncSessionLocal() as db:
            res = await db.execute(stmt)
            return list(res.scalars().all())

    async def create_skill(
        self,
        skill_obj: Skill,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Skill:
        """Create new Skill and write AuditLog."""
        async def _execute_create(db: AsyncSession):
            db.add(skill_obj)
            await db.flush()

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="SKILL_CREATED",
                entity="Skill",
                entity_id=str(skill_obj.id),
                reason=f"Created skill {skill_obj.skill_name} in category {skill_obj.category}",
                new_value=f"Name: {skill_obj.skill_name}, Category: {skill_obj.category}, Status: {skill_obj.status}",
            )
            db.add(audit)
            await db.commit()
            return skill_obj

        if self.session:
            return await _execute_create(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_create(db_session)

    async def update_skill(
        self,
        skill_obj: Skill,
        old_summary: str,
        new_summary: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Skill:
        """Update existing Skill and write AuditLog."""
        async def _execute_update(db: AsyncSession):
            skill_obj.updated_at = datetime.now(timezone.utc)
            db.add(skill_obj)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="SKILL_UPDATED",
                entity="Skill",
                entity_id=str(skill_obj.id),
                reason=f"Updated skill {skill_obj.skill_name}",
                old_value=old_summary,
                new_value=new_summary,
            )
            db.add(audit)
            await db.commit()
            return skill_obj

        if self.session:
            return await _execute_update(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_update(db_session)

    async def update_status(
        self,
        skill_obj: Skill,
        old_status: str,
        new_status: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Skill:
        """Update skill status and write AuditLog."""
        async def _execute_status(db: AsyncSession):
            skill_obj.status = new_status
            skill_obj.updated_at = datetime.now(timezone.utc)
            db.add(skill_obj)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="SKILL_STATUS_CHANGED",
                entity="Skill",
                entity_id=str(skill_obj.id),
                reason=f"Skill {skill_obj.skill_name} status changed from {old_status} to {new_status}",
                old_value=f"status={old_status}",
                new_value=f"status={new_status}",
            )
            db.add(audit)
            await db.commit()
            return skill_obj

        if self.session:
            return await _execute_status(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_status(db_session)
