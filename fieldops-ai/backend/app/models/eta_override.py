"""
ETA Override ORM model for Module 11.
Tracks dispatcher manual overrides of system ETA recommendations with full audit trace.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.technician import Technician
    from app.models.user import User


class ETAOverride(Base, UUIDMixin):
    """
    Stores historical and active manual ETA overrides applied by dispatchers.
    Never silently replaces system ETA recommendations.
    """

    __tablename__ = "eta_overrides"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    technician_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("technicians.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dispatcher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_system_eta: Mapped[int] = mapped_column(Integer, nullable=False)
    overridden_eta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    previous_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="eta_overrides")
    dispatcher: Mapped["User"] = relationship("User")
    technician: Mapped[Optional["Technician"]] = relationship("Technician")

    def __repr__(self) -> str:
        return f"<ETAOverride(id={self.id}, job_id={self.job_id}, overridden_eta={self.overridden_eta})>"
