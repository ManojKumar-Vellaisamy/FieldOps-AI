"""
Pydantic schemas for Smart Technician Assignment DTOs, request payloads, and candidate responses.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CandidateTechnicianResponse(BaseModel):
    """Detailed candidate technician evaluation result."""

    technician_id: UUID
    employee_code: str
    full_name: str
    availability_status: str
    primary_skill_name: Optional[str] = None
    years_experience: int = 0
    current_workload: int = 0
    is_eligible: bool = True
    ineligibility_reason: Optional[str] = None
    distance_display: str = "Distance unavailable"
    recommendation_score: float = 0.0
    ranking: int = 1
    explanation_reasons: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AssignmentRecommendationResponse(BaseModel):
    """Full Smart Assignment recommendation calculation result."""

    job_id: UUID
    job_number: str
    customer_name: Optional[str] = None
    priority: Optional[str] = None
    address: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    assignment_status: Optional[str] = "UNASSIGNED"
    required_skill_name: Optional[str] = None
    recommended_technician: Optional[CandidateTechnicianResponse] = None
    recommendation_score: Optional[float] = None
    ranked_candidates: list[CandidateTechnicianResponse] = Field(default_factory=list)
    alternative_technicians: list[CandidateTechnicianResponse] = Field(default_factory=list)
    explanation: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class AssignmentCreatePayload(BaseModel):
    """Payload for Dispatcher confirming technician assignment."""

    technician_id: UUID = Field(...)


class AssignmentResponse(BaseModel):
    """Representation of an Assignment entity."""

    id: UUID
    job_id: UUID
    technician_id: UUID
    assigned_by: Optional[UUID] = None
    assignment_type: str
    assignment_status: str
    assigned_at: datetime
    technician_name: Optional[str] = None
    job_number: Optional[str] = None

    model_config = {"from_attributes": True}
