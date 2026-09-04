"""
Skill ORM model.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.technician import Technician


class Skill(Base, UUIDMixin):
    """Skill taxonomy model."""

    __tablename__ = "skills"

    skill_name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    technicians: Mapped[list["Technician"]] = relationship("Technician", back_populates="primary_skill")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="required_skill")

    @property
    def is_active(self) -> bool:
        """Returns True if the skill is in ACTIVE status."""
        return self.status == "ACTIVE"

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, skill_name='{self.skill_name}', category='{self.category}', status='{self.status}')>"
