"""
User repository layer providing database data access for authentication & user management.
"""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models.user import User


class UserRepository:
    """Repository for querying User entities from PostgreSQL database."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        """Fetch user entity by email from PostgreSQL database."""
        normalized_email = email.strip().lower()

        if self.session:
            stmt = select(User).where(User.email == normalized_email)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        async with AsyncSessionLocal() as db_session:
            stmt = select(User).where(User.email == normalized_email)
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID | str) -> User | None:
        """Fetch user entity by UUID from PostgreSQL database."""
        target_uuid = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id

        if self.session:
            stmt = select(User).where(User.id == target_uuid)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        async with AsyncSessionLocal() as db_session:
            stmt = select(User).where(User.id == target_uuid)
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_password(
        self,
        user_id: uuid.UUID | str,
        new_password_hash: str,
        must_change_password: bool = False,
    ) -> bool:
        """Update password hash and must_change_password flag for a user."""
        target_uuid = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id

        async def _do_update(db: AsyncSession) -> bool:
            stmt = select(User).where(User.id == target_uuid)
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                return False
            user.password_hash = new_password_hash
            user.must_change_password = must_change_password
            db.add(user)
            await db.commit()
            return True

        if self.session:
            return await _do_update(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _do_update(db_session)

    async def update_profile(
        self,
        user_id: uuid.UUID | str,
        full_name: str | None = None,
        phone: str | None = None,
    ) -> User | None:
        """Update full_name and/or phone for a user."""
        target_uuid = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id

        async def _do_update(db: AsyncSession) -> User | None:
            stmt = select(User).where(User.id == target_uuid)
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                return None
            if full_name is not None:
                user.full_name = full_name.strip()
            if phone is not None:
                user.phone = phone.strip() if phone else None
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return user

        if self.session:
            return await _do_update(self.session)

        async with AsyncSessionLocal() as db_session:
            return await _do_update(db_session)

