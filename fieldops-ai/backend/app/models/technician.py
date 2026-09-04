"""
Technician ORM model.
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.skill import Skill
    from app.models.user import User


class Technician(Base, UUIDMixin, TimestampMixin):
    """Field technician profile model."""

    __tablename__ = "technicians"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    primary_skill_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    years_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    availability_status: Mapped[str] = mapped_column(String(50), default="AVAILABLE", nullable=False)
    current_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="technician")
    primary_skill: Mapped[Optional["Skill"]] = relationship("Skill", back_populates="technicians")
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="technician", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Technician(id={self.id}, employee_code='{self.employee_code}')>"
