"""
Pydantic schemas for Skill management DTOs, validations, and paginated responses.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SkillResponse(BaseModel):
    """Complete representation of a Skill entity."""

    id: UUID
    skill_name: str
    category: str
    description: Optional[str] = None
    status: str = "ACTIVE"
    technician_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SkillCreate(BaseModel):
    """Request payload for creating a new Skill."""

    skill_name: str = Field(..., min_length=2, max_length=100)
    category: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    status: str = Field(default="ACTIVE")

    @field_validator("skill_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Skill name cannot be empty or whitespace only.")
        return clean

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Category cannot be empty or whitespace only.")
        return clean

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean not in ("ACTIVE", "INACTIVE"):
            raise ValueError("Status must be either 'ACTIVE' or 'INACTIVE'.")
        return clean


class SkillUpdate(BaseModel):
    """Request payload for updating an existing Skill."""

    skill_name: Optional[str] = Field(None, min_length=2, max_length=100)
    category: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[str] = None

    @field_validator("skill_name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("Skill name cannot be empty.")
            return clean
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("Category cannot be empty.")
            return clean
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().upper()
            if clean not in ("ACTIVE", "INACTIVE"):
                raise ValueError("Status must be either 'ACTIVE' or 'INACTIVE'.")
            return clean
        return v


class SkillStatusPatch(BaseModel):
    """Request payload for patching skill active/inactive status."""

    status: str = Field(...)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean not in ("ACTIVE", "INACTIVE"):
            raise ValueError("Status must be either 'ACTIVE' or 'INACTIVE'.")
        return clean


class PaginatedSkillResponse(BaseModel):
    """Paginated result for skill queries."""

    items: list[SkillResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    total_active: int = 0
    total_inactive: int = 0


class SkillTechnicianSummary(BaseModel):
    """Simplified technician details associated with a skill."""

    id: UUID
    employee_code: str
    full_name: str
    email: str
    years_experience: int
    availability_status: str

    model_config = {"from_attributes": True}


class SkillWithTechniciansResponse(BaseModel):
    """Skill detail response including list of qualified technicians."""

    skill: SkillResponse
    technicians: list[SkillTechnicianSummary]
    technician_count: int
