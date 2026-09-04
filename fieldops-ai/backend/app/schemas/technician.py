"""
Pydantic schemas for Technician management DTOs, validation, and paginated responses.
"""

from datetime import datetime
import re
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


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
    phone: Optional[str] = Field(None, example="+1 (555) 019-2834")
    primary_skill_id: UUID = Field(..., description="Primary Skill UUID is required")
    years_experience: int = Field(default=0, ge=0, example=5)
    availability_status: str = Field(default="AVAILABLE", example="AVAILABLE")
    current_latitude: Optional[float] = Field(None, example=37.7749)
    current_longitude: Optional[float] = Field(None, example=-122.4194)

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

