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
