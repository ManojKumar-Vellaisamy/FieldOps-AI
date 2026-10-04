"""
Pydantic schemas for Technician management DTOs, validation, and paginated responses.
"""

from datetime import datetime, timedelta, timezone
import re
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class SkillSummary(BaseModel):
    """Simplified Skill DTO embedded in responses."""

    id: UUID
    skill_name: str
    category: str

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    """Simplified User DTO embedded in responses."""

    id: UUID
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


class TechnicianResponse(BaseModel):
    """Complete Technician representation DTO."""

    id: UUID
    user_id: UUID
    employee_code: str
    primary_skill_id: Optional[UUID] = None
    years_experience: int
    availability_status: str
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    location_updated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Embedded relationships
    user: Optional[UserSummary] = None
    primary_skill: Optional[SkillSummary] = None

    model_config = {"from_attributes": True}


class TechnicianCreate(BaseModel):
    """Request payload for creating a new Technician and User account."""

    employee_code: str = Field(..., min_length=2, max_length=50, example="TECH-101")
    full_name: str = Field(..., min_length=2, max_length=255, example="Alex Rivera")
    email: EmailStr = Field(..., example="technician@fieldops.ai")
    password: str = Field(..., min_length=8, example="Tech@123")
    confirm_password: Optional[str] = Field(None, min_length=8, example="Tech@123")
    phone: Optional[str] = Field(None, example="+1 (555) 019-2834")
    primary_skill_id: UUID = Field(..., description="Primary Skill UUID is required")
    years_experience: int = Field(default=0, ge=0, example=5)
    availability_status: str = Field(default="AVAILABLE", example="AVAILABLE")
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None

    @model_validator(mode="after")
    def check_passwords_match(self) -> "TechnicianCreate":
        if self.confirm_password and self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v:
            clean_v = v.strip()
            if not re.match(r"^\+?[\d\s\-\(\)]{7,20}$", clean_v):
                raise ValueError("Invalid phone number format.")
            return clean_v
        return v

    @field_validator("years_experience")
    @classmethod
    def validate_experience(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Years of experience cannot be negative.")
        return v



class TechnicianDependencyCheckResponse(BaseModel):
    """Dependency inspection result before technician deletion."""

    technician_id: UUID
    employee_code: str
    has_dependencies: bool
    assignment_count: int
    eta_override_count: int
    can_delete: bool
    reason: Optional[str] = None
    blockers: list[str] = Field(default_factory=list)



class TechnicianUpdate(BaseModel):
    """Request payload for updating technician profile."""

    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    primary_skill_id: Optional[UUID] = None
    years_experience: Optional[int] = Field(None, ge=0)
    availability_status: Optional[str] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v:
            clean_v = v.strip()
            if not re.match(r"^\+?[\d\s\-\(\)]{7,20}$", clean_v):
                raise ValueError("Invalid phone number format.")
            return clean_v
        return v

    @field_validator("years_experience")
    @classmethod
    def validate_experience(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Years of experience cannot be negative.")
        return v


class TechnicianStatusPatch(BaseModel):
    """Request payload for updating technician availability status."""

    availability_status: str = Field(..., example="AVAILABLE")


class TechnicianLocationPatch(BaseModel):
    """Request payload for updating technician GPS location telemetry."""

    latitude: float = Field(..., ge=-90.0, le=90.0, example=37.7749)
    longitude: float = Field(..., ge=-180.0, le=180.0, example=-122.4194)
    recorded_at: Optional[datetime] = Field(
        None,
        description="Observation timestamp from client device GNSS fix (ISO-8601 UTC).",
        example="2026-09-19T08:30:00Z",
    )

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        # Ensure timezone-aware (assume UTC if naive)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)

        now = datetime.now(timezone.utc)
        # Reject future timestamps beyond reasonable clock drift tolerance (e.g. 300 seconds / 5 min)
        if v > now + timedelta(seconds=300):
            raise ValueError("recorded_at timestamp cannot be in the future (max 300s clock drift allowed).")
        return v


class PaginatedTechnicianResponse(BaseModel):
    """Paginated result for technician listing queries."""

    items: list[TechnicianResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TechnicianSkillsResponse(BaseModel):
    """Technician skill association response DTO."""

    technician_id: UUID
    employee_code: str
    primary_skill: Optional[SkillSummary] = None
    skills: list[SkillSummary] = Field(default_factory=list)

    model_config = {"from_attributes": True}

