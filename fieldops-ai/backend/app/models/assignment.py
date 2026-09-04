"""
Assignment ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDMixin
from app.models.enums import AssignmentType

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.technician import Technician
    from app.models.user import User


class Assignment(Base, UUIDMixin):
    """Job assignment model linking jobs with technicians."""

    __tablename__ = "assignments"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    technician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("technicians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignment_type: Mapped[AssignmentType] = mapped_column(
        SQLEnum(AssignmentType, name="assignment_type_enum", native_enum=False),
        default=AssignmentType.MANUAL,
        nullable=False,
    )
    predicted_eta: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    assignment_status: Mapped[str] = mapped_column(String(50), default="ASSIGNED", nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="assignments")
    technician: Mapped["Technician"] = relationship("Technician", back_populates="assignments")
    assigner: Mapped[Optional["User"]] = relationship(
        "User", back_populates="assigned_assignments", foreign_keys=[assigned_by]
    )

    def __repr__(self) -> str:
        return f"<Assignment(id={self.id}, job_id={self.job_id}, technician_id={self.technician_id})>"
