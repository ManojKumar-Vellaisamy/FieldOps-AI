"""
Technician Repository Layer providing data access, filtering, pagination, and audit logging.
"""

from typing import Optional
import uuid
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.role import Role
from app.models.skill import Skill
from app.models.technician import Technician
from app.models.user import User, UserStatus


class TechnicianRepository:
    """Data access layer for Technician & User entities."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def get_by_id(self, tech_id: uuid.UUID) -> Optional[Technician]:
        """Fetch technician profile by ID eagerly loading user and primary_skill."""
        stmt = (
            select(Technician)
            .options(
                selectinload(Technician.user),
                selectinload(Technician.primary_skill),
            )
            .where(Technician.id == tech_id)
        )
        if self.session:
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> Optional[Technician]:
        """Fetch technician profile by associated User ID."""
        stmt = (
            select(Technician)
            .options(
                selectinload(Technician.user),
                selectinload(Technician.primary_skill),
            )
            .where(Technician.user_id == user_id)
        )
        if self.session:
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_employee_code(self, employee_code: str) -> Optional[Technician]:
        """Check if an employee code already exists."""
        code_clean = employee_code.strip().upper()
        stmt = select(Technician).where(func.upper(Technician.employee_code) == code_clean)
        if self.session:
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Check if a user email already exists."""
        email_clean = email.strip().lower()
        stmt = select(User).where(func.lower(User.email) == email_clean)
        if self.session:
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_role_by_name(self, role_name: str) -> Optional[Role]:
        """Fetch Role entity by name."""
        stmt = select(Role).where(Role.name == role_name)
        if self.session:
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_skill_by_id(self, skill_id: uuid.UUID) -> Optional[Skill]:
        """Fetch Skill entity by ID."""
        stmt = select(Skill).where(Skill.id == skill_id)
        if self.session:
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_technicians(
        self,
        search: Optional[str] = None,
        availability_status: Optional[str] = None,
        skill_id: Optional[uuid.UUID] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[Technician], int]:
        """Paginated, filtered, and sorted query for technicians."""
        async def _execute_query(db: AsyncSession):
            query = (
                select(Technician)
                .join(User, Technician.user_id == User.id)
                .options(
                    selectinload(Technician.user),
                    selectinload(Technician.primary_skill),
                )
            )

            # Filtering
            filters = []
            if search and search.strip():
                s = f"%{search.strip()}%"
                filters.append(
                    or_(
                        Technician.employee_code.ilike(s),
                        User.full_name.ilike(s),
                        User.email.ilike(s),
                    )
                )

            if availability_status and availability_status.strip() and availability_status != "ALL":
                filters.append(Technician.availability_status == availability_status.strip().upper())

            if skill_id:
                filters.append(Technician.primary_skill_id == skill_id)

            if filters:
                query = query.where(*filters)

            # Count total matching rows
            count_query = select(func.count(Technician.id)).join(User, Technician.user_id == User.id)
            if filters:
                count_query = count_query.where(*filters)

            total = (await db.execute(count_query)).scalar() or 0

            # Sorting
            sort_attr = getattr(Technician, sort_by, None)
            if sort_attr is None:
                if sort_by == "name":
                    sort_attr = User.full_name
                else:
                    sort_attr = Technician.created_at

            if sort_order.lower() == "asc":
                query = query.order_by(sort_attr.asc())
            else:
                query = query.order_by(sort_attr.desc())

            # Pagination
            offset = (max(page, 1) - 1) * page_size
            query = query.offset(offset).limit(page_size)

            result = await db.execute(query)
            items = list(result.scalars().all())
            return items, total

        if self.session:
            return await _execute_query(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_query(db_session)

    async def create_technician_with_user(
        self,
        user_obj: User,
        tech_obj: Technician,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Technician:
        """Create User and Technician profile within a single transaction and write AuditLog."""
        async def _execute_create(db: AsyncSession):
            db.add(user_obj)
            await db.flush()

            tech_obj.user_id = user_obj.id
            db.add(tech_obj)
            await db.flush()

            # Create AuditLog entry
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="TECHNICIAN_CREATED",
                entity="Technician",
                entity_id=str(tech_obj.id),
                reason=f"Created technician {tech_obj.employee_code} ({user_obj.full_name})",
                new_value=f"Code: {tech_obj.employee_code}, Email: {user_obj.email}, Role: Technician",
            )
            db.add(audit)
            await db.commit()

            # Re-fetch eagerly loaded object
            return await self.get_by_id(tech_obj.id)

        if self.session:
            return await _execute_create(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_create(db_session)

    async def update_technician_with_user(
        self,
        tech_obj: Technician,
        user_obj: User,
        old_val_summary: str,
        new_val_summary: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Technician:
        """Update Technician profile and User details with AuditLog."""
        async def _execute_update(db: AsyncSession):
            db.add(user_obj)
            db.add(tech_obj)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="TECHNICIAN_UPDATED",
                entity="Technician",
                entity_id=str(tech_obj.id),
                reason=f"Updated technician {tech_obj.employee_code}",
                old_value=old_val_summary,
                new_value=new_val_summary,
            )
            db.add(audit)
            await db.commit()

            return await self.get_by_id(tech_obj.id)

        if self.session:
            return await _execute_update(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_update(db_session)

    async def update_status(
        self,
        tech_obj: Technician,
        old_status: str,
        new_status: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Technician:
        """Update availability status of technician with AuditLog."""
        async def _execute_status_update(db: AsyncSession):
            tech_obj.availability_status = new_status
            db.add(tech_obj)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="TECHNICIAN_STATUS_CHANGED",
                entity="Technician",
                entity_id=str(tech_obj.id),
                reason=f"Status changed from {old_status} to {new_status}",
                old_value=f"availability_status={old_status}",
                new_value=f"availability_status={new_status}",
            )
            db.add(audit)
            await db.commit()

            return await self.get_by_id(tech_obj.id)

        if self.session:
            return await _execute_status_update(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_status_update(db_session)

    async def delete_technician(
        self,
        tech_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Deactivate/delete technician and generate AuditLog."""
        async def _execute_delete(db: AsyncSession):
            tech_obj = await db.get(Technician, tech_id)
            if not tech_obj:
                return

            old_availability = tech_obj.availability_status
            user_obj = await db.get(User, tech_obj.user_id)
            old_user_status = user_obj.status.value if user_obj and hasattr(user_obj.status, "value") else "ACTIVE"

            if user_obj:
                user_obj.status = UserStatus.INACTIVE
                db.add(user_obj)

            tech_obj.availability_status = "INACTIVE"
            db.add(tech_obj)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="TECHNICIAN_DEACTIVATED",
                entity="Technician",
                entity_id=str(tech_obj.id),
                reason=f"Deactivated technician {tech_obj.employee_code}",
                old_value=f"status={old_user_status}, availability={old_availability}",
                new_value="status=INACTIVE, availability=INACTIVE",
            )
            db.add(audit)
            await db.commit()

        if self.session:
            await _execute_delete(self.session)
        else:
            async with AsyncSessionLocal() as db_session:
                await _execute_delete(db_session)


