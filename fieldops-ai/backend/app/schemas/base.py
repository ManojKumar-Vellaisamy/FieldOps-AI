"""
Pydantic base schemas shared across all domain schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base Pydantic schema with ORM mode enabled."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class BaseEntitySchema(BaseSchema):
    """Schema for ORM entities that have UUID pk and audit timestamps."""

    id: UUID
    created_at: datetime
    updated_at: datetime
