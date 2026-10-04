"""
Pydantic schemas for Audit Log DTOs and paginated query responses.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AuditUserSummary(BaseModel):
    """Simplified user details for audit log representations."""

    id: UUID
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    """Complete representation of an AuditLog entity."""

    id: UUID
    user_id: Optional[UUID] = None
    user_full_name: Optional[str] = None
    action: str = Field(..., example="TECHNICIAN_ASSIGNED")
    entity: str = Field(..., example="Job")
    entity_id: Optional[str] = Field(None, example="3d95958b-41ca-4408-9d84-c84db4636a7a")
    reason: Optional[str] = Field(None, example="Assigned technician via smart dispatch")
    old_value: Optional[str] = Field(None)
    new_value: Optional[str] = Field(None)
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedAuditLogResponse(BaseModel):
    """Paginated result for audit log queries."""

    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
