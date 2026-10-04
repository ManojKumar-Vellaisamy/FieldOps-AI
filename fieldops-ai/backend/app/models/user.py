"""
User ORM model.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import UserRole, UserStatus

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.audit_log import AuditLog
    from app.models.job import Job
    from app.models.role import Role
    from app.models.technician import Technician


class User(Base, UUIDMixin, TimestampMixin):
    """Platform user model."""

    __tablename__ = "users"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        SQLEnum(UserStatus, name="user_status_enum", native_enum=False),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    role_rel: Mapped["Role"] = relationship(
        "Role", back_populates="users", lazy="joined"
    )
    technician: Mapped[Optional["Technician"]] = relationship(
        "Technician", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    created_jobs: Mapped[list["Job"]] = relationship(
        "Job", back_populates="creator", foreign_keys="Job.created_by"
    )
    assigned_assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="assigner", foreign_keys="Assignment.assigned_by"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user")

    @property
    def role(self) -> str:
        """Returns the security role name string for authentication & authorization."""
        if hasattr(self, "_role_override") and self._role_override:
            return self._role_override
        if self.role_rel and hasattr(self.role_rel, "name"):
            return self.role_rel.name
        return UserRole.DISPATCHER.value

    @property
    def is_active(self) -> bool:
        """Compatibility property checking if user account status is ACTIVE."""
        return self.status == UserStatus.ACTIVE

    @property
    def hashed_password(self) -> str:
        """Getter compatibility alias for password_hash."""
        return self.password_hash

    @hashed_password.setter
    def hashed_password(self, value: str) -> None:
        """Setter compatibility alias for password_hash."""
        self.password_hash = value

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', full_name='{self.full_name}')>"


__all__ = ["User", "UserRole", "UserStatus"]
