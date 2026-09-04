"""
Role ORM model.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class Role(Base, UUIDMixin, TimestampMixin):
    """Role model representing security access roles."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="role_rel")

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}')>"
