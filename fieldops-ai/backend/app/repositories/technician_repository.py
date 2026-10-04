"""
Technician Repository Layer providing data access, filtering, pagination, and audit logging.
"""

from datetime import datetime, timezone
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
            target_user = await db.merge(user_obj)
            await db.flush()

            tech_obj.user_id = target_user.id
            db.add(tech_obj)
            await db.flush()

            # Create AuditLog entry
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="TECHNICIAN_CREATED",
                entity="Technician",
                entity_id=str(tech_obj.id),
                reason=f"Created technician {tech_obj.employee_code} ({target_user.full_name})",
                new_value=f"Code: {tech_obj.employee_code}, Email: {target_user.email}, Role: Technician",
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

    async def update_location(
        self,
        tech_obj: Technician,
        latitude: float,
        longitude: float,
        recorded_at: Optional[datetime] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Technician:
        """Update technician current latitude, longitude, and location_updated_at telemetry without audit table pollution."""
        async def _execute_location_update(db: AsyncSession):
            tech_obj.current_latitude = latitude
            tech_obj.current_longitude = longitude
            tech_obj.location_updated_at = recorded_at if recorded_at is not None else datetime.now(timezone.utc)
            db.add(tech_obj)
            await db.commit()

            return await self.get_by_id(tech_obj.id)

        if self.session:
            return await _execute_location_update(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _execute_location_update(db_session)

    async def delete_technician(
        self,
        tech_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Deactivate technician profile and linked user account with AuditLog."""
        await self.deactivate_technician(tech_id, actor_id=actor_id)

    async def activate_technician(
        self,
        tech_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Optional[Technician]:
        """Activate technician profile and linked user account with AuditLog."""
        async def _execute_activate(db: AsyncSession):
            tech_obj = await db.get(Technician, tech_id)
            if not tech_obj:
                return None

            user_obj = await db.get(User, tech_obj.user_id)
            old_availability = tech_obj.availability_status
            old_user_status = user_obj.status.value if user_obj and hasattr(user_obj.status, "value") else "INACTIVE"

            if user_obj:
                user_obj.status = UserStatus.ACTIVE
                db.add(user_obj)

            tech_obj.availability_status = "AVAILABLE"
            db.add(tech_obj)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="TECHNICIAN_ACTIVATED",
                entity="Technician",
                entity_id=str(tech_obj.id),
                reason=f"Activated technician {tech_obj.employee_code}",
                old_value=f"status={old_user_status}, availability={old_availability}",
                new_value="status=ACTIVE, availability=AVAILABLE",
            )
            db.add(audit)
            await db.commit()

            return await self.get_by_id(tech_obj.id)

        if self.session:
            return await _execute_activate(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute_activate(db_session)

    async def deactivate_technician(
        self,
        tech_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Optional[Technician]:
        """Deactivate technician profile and linked user account with AuditLog."""
        async def _execute_deactivate(db: AsyncSession):
            tech_obj = await db.get(Technician, tech_id)
            if not tech_obj:
                return None

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

            return await self.get_by_id(tech_obj.id)

        if self.session:
            return await _execute_deactivate(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute_deactivate(db_session)

    async def check_dependencies(self, tech_id: uuid.UUID) -> dict:
        """Inspect if technician has active or historical assignments or overrides."""
        from app.core.exceptions import NotFoundError
        from app.models.assignment import Assignment
        from app.models.eta_override import ETAOverride

        async def _execute_check(db: AsyncSession):
            tech = await db.get(Technician, tech_id)
            if not tech:
                raise NotFoundError("Technician", str(tech_id))

            asg_stmt = select(func.count(Assignment.id)).where(Assignment.technician_id == tech_id)
            asg_count = (await db.execute(asg_stmt)).scalar() or 0

            eta_stmt = select(func.count(ETAOverride.id)).where(ETAOverride.technician_id == tech_id)
            eta_count = (await db.execute(eta_stmt)).scalar() or 0

            has_deps = asg_count > 0 or eta_count > 0
            reason = None
            if has_deps:
                parts = []
                if asg_count > 0:
                    parts.append(f"{asg_count} operational assignment record(s)")
                if eta_count > 0:
                    parts.append(f"{eta_count} ETA override record(s)")
                reason = (
                    f"Technician '{tech.employee_code}' has {', '.join(parts)}. "
                    f"Permanent deletion is prohibited to protect historical operational records. "
                    f"Deactivate the technician instead."
                )

            return {
                "technician_id": tech.id,
                "employee_code": tech.employee_code,
                "has_dependencies": has_deps,
                "assignment_count": asg_count,
                "eta_override_count": eta_count,
                "can_delete": not has_deps,
                "reason": reason,
                "blockers": parts if has_deps else [],
            }


        if self.session:
            return await _execute_check(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute_check(db_session)

    async def permanent_delete_technician(
        self,
        tech_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """Permanently delete a technician with zero operational dependencies."""
        from sqlalchemy import delete
        from app.core.exceptions import ConflictError, NotFoundError
        from app.models.assignment import Assignment
        from app.models.eta_override import ETAOverride

        async def _execute_perm_delete(db: AsyncSession):
            tech = await db.get(Technician, tech_id)
            if not tech:
                raise NotFoundError("Technician", str(tech_id))

            # Dependency check
            asg_stmt = select(func.count(Assignment.id)).where(Assignment.technician_id == tech_id)
            asg_count = (await db.execute(asg_stmt)).scalar() or 0
            eta_stmt = select(func.count(ETAOverride.id)).where(ETAOverride.technician_id == tech_id)
            eta_count = (await db.execute(eta_stmt)).scalar() or 0

            if asg_count > 0 or eta_count > 0:
                raise ConflictError(
                    f"Cannot permanently delete technician '{tech.employee_code}' because they have "
                    f"active or historical operational records ({asg_count} assignments, {eta_count} ETA overrides). "
                    f"Please Deactivate the technician instead to preserve historical integrity."
                )

            employee_code = tech.employee_code
            user_id = tech.user_id

            # Delete audit logs related to technician entity
            del_audit = delete(AuditLog).where(
                (AuditLog.entity == "Technician") & (AuditLog.entity_id == str(tech_id))
            )
            await db.execute(del_audit)

            # Delete technician record
            await db.delete(tech)
            await db.flush()

            # If user is not one of the baseline system accounts, delete user record too
            user = await db.get(User, user_id)
            if user and user.email.lower() not in {"admin@fieldops.ai", "dispatcher@fieldops.ai", "technician@fieldops.ai"}:
                await db.delete(user)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="TECHNICIAN_PERMANENTLY_DELETED",
                entity="Technician",
                entity_id=str(tech_id),
                reason=f"Permanently deleted technician {employee_code} (Zero operational dependencies)",
            )
            db.add(audit)
            await db.commit()
            return {"message": f"Technician {employee_code} permanently deleted successfully."}

        if self.session:
            return await _execute_perm_delete(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute_perm_delete(db_session)

    async def reset_technician_password(
        self,
        tech_id: uuid.UUID,
        new_password_hash: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Optional[Technician]:
        """Reset technician user password to new temporary password with AuditLog."""
        from app.core.exceptions import NotFoundError

        async def _execute_reset(db: AsyncSession):
            tech = await db.get(Technician, tech_id)
            if not tech:
                raise NotFoundError("Technician", str(tech_id))

            user = await db.get(User, tech.user_id)
            if not user:
                raise NotFoundError("User", str(tech.user_id))

            user.password_hash = new_password_hash
            user.must_change_password = True
            db.add(user)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="TECHNICIAN_PASSWORD_RESET",
                entity="Technician",
                entity_id=str(tech.id),
                reason=f"Administrator reset password for technician {tech.employee_code} ({user.email})",
                old_value="password_hash=[PROTECTED]",
                new_value="password_hash=[PROTECTED], must_change_password=True",
            )
            db.add(audit)
            await db.commit()

            return await self.get_by_id(tech.id)

        if self.session:
            return await _execute_reset(self.session)
        async with AsyncSessionLocal() as db_session:
            return await _execute_reset(db_session)



