"""
Job ORM model.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import JobStatus, Priority

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.eta_override import ETAOverride
    from app.models.skill import Skill
    from app.models.user import User


class Job(Base, UUIDMixin, TimestampMixin):
    """Field service job / work order model."""

    __tablename__ = "jobs"

    job_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    required_skill_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    priority: Mapped[Priority] = mapped_column(
        SQLEnum(Priority, name="priority_enum", native_enum=False),
        default=Priority.MEDIUM,
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, name="job_status_enum", native_enum=False),
        default=JobStatus.NEW,
        nullable=False,
    )
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    required_skill: Mapped[Optional["Skill"]] = relationship("Skill", back_populates="jobs")
    creator: Mapped[Optional["User"]] = relationship(
        "User", back_populates="created_jobs", foreign_keys=[created_by]
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="job", cascade="all, delete-orphan"
    )
    eta_overrides: Mapped[list["ETAOverride"]] = relationship(
        "ETAOverride", back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def service_instructions(self) -> Optional[str]:
        """Alias property for service_instructions matching domain requirements."""
        return self.description

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, job_number='{self.job_number}', status='{self.status}')>"

