"""
Pydantic schemas for Job Management DTOs, request payloads, and paginated responses.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import JobStatus, Priority
from app.schemas.skill import SkillResponse


class JobCreatorSummary(BaseModel):
    """Simplified creator user details."""

    id: UUID
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class JobAssignedTechnicianSummary(BaseModel):
    """Simplified technician details assigned to job."""

    id: UUID
    employee_code: str
    full_name: str

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    """Complete representation of a Job entity."""

    id: UUID
    job_number: str
    customer_name: str
    customer_phone: Optional[str] = None
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    required_skill_id: Optional[UUID] = None
    required_skill: Optional[SkillResponse] = None
    priority: Priority
    status: JobStatus
    scheduled_time: Optional[datetime] = None
    description: Optional[str] = None
    service_instructions: Optional[str] = None
    created_by: Optional[UUID] = None
    creator: Optional[JobCreatorSummary] = None
    assigned_technician: Optional[JobAssignedTechnicianSummary] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobCreate(BaseModel):
    """Request payload for Dispatcher creating a new job."""

    customer_name: str = Field(..., min_length=2, max_length=255)
    customer_phone: Optional[str] = Field(None, max_length=50)
    address: str = Field(..., min_length=2)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    required_skill_id: UUID = Field(...)
    priority: Priority = Field(default=Priority.MEDIUM)
    scheduled_time: Optional[datetime] = Field(None)
    description: Optional[str] = Field(None, max_length=2000)
    service_instructions: Optional[str] = Field(None, max_length=2000)

    @field_validator("customer_name")
    @classmethod
    def validate_customer_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Customer name cannot be empty or whitespace only.")
        return clean

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Address cannot be empty or whitespace only.")
        return clean


class JobUpdate(BaseModel):
    """Request payload for updating eligible job fields."""

    customer_name: Optional[str] = Field(None, min_length=2, max_length=255)
    customer_phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, min_length=5)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    required_skill_id: Optional[UUID] = Field(None)
    priority: Optional[Priority] = Field(None)
    scheduled_time: Optional[datetime] = Field(None)
    description: Optional[str] = Field(None, max_length=2000)
    service_instructions: Optional[str] = Field(None, max_length=2000)


    @field_validator("customer_name")
    @classmethod
    def validate_customer_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("Customer name cannot be empty.")
            return clean
        return v

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("Address cannot be empty.")
            return clean
        return v


class JobStatusPatch(BaseModel):
    """Request payload for status transition."""

    status: str = Field(...)
    notes: Optional[str] = Field(None, max_length=2000)
    completion_notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("status", mode="before")
    @classmethod
    def parse_status_alias(cls, v: str | JobStatus) -> str:
        if isinstance(v, JobStatus):
            v = v.value
        s = str(v).strip().upper()
        if s == "EN_ROUTE":
            return "TRAVELLING"
        if s == "IN_PROGRESS":
            return "WORKING"
        return s



class JobCancelPayload(BaseModel):
    """Request payload for job cancellation."""

    reason: str = Field(..., min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Cancellation reason is required.")
        return clean


class PaginatedJobResponse(BaseModel):
    """Paginated result for job queries."""

    items: list[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
