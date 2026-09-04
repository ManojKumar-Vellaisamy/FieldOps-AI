"""
Pydantic schemas for Context-Aware ETA Engine (Module 11 Upgrade).
Provides structured definitions for factors, data sources, calculation parameters,
dispatcher overrides, experiment performance evaluation, and fully explainable ETA responses.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContextFactor(BaseModel):
    """Specific operational context factor affecting the baseline ETA."""

    model_config = ConfigDict(from_attributes=True)

    category: str = Field(..., description="Factor category: TRAVEL, WEATHER, TRAFFIC, EVENTS, ROAD, GPS, AVAILABILITY")
    factor: str = Field(..., description="Short identifier of the factor")
    impact_minutes: int = Field(..., description="Minutes added or subtracted (+ / -)")
    description: str = Field(..., description="Human-readable explanation of the operational condition")


class DataSource(BaseModel):
    """Represents one context data source and its current operational status."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Display name of the data source (e.g. 'Traffic Data')")
    status: str = Field(
        ...,
        description="Source status: AVAILABLE | STALE | UNAVAILABLE | INVALID",
    )
    description: str = Field(..., description="Operational explanation of the source status")
    impact_minutes: int = Field(
        0, description="ETA adjustment this source contributed (0 when UNAVAILABLE/STALE/INVALID)"
    )
    sampled_at: Optional[str] = Field(None, description="ISO-8601 UTC timestamp when this source was evaluated")
    category: str = Field("UNKNOWN", description="Source category: GPS, WEATHER, TRAFFIC, EVENTS, ROAD")


class ETAOverrideCreate(BaseModel):
    """Payload to apply a dispatcher manual override on a job's ETA."""

    overridden_eta: int = Field(..., ge=1, le=1440, description="Dispatcher manual ETA override value in minutes")
    reason: str = Field(..., min_length=3, max_length=1000, description="Mandatory dispatcher operational rationale for override")


class ETAOverrideResponse(BaseModel):
    """Dispatcher manual ETA override record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Override record UUID")
    job_id: UUID = Field(..., description="Target job UUID")
    technician_id: Optional[UUID] = Field(None, description="Assigned technician UUID")
    dispatcher_id: UUID = Field(..., description="Dispatcher user UUID who authorized override")
    dispatcher_name: Optional[str] = Field(None, description="Dispatcher full name")
    original_system_eta: int = Field(..., description="Original context-aware system recommendation ETA in minutes")
    overridden_eta: int = Field(..., description="Manual dispatcher ETA in minutes")
    reason: str = Field(..., description="Dispatcher operational rationale")
    previous_value: Optional[str] = Field(None, description="Previous system value summary")
    new_value: Optional[str] = Field(None, description="New override value summary")
    created_at: datetime = Field(..., description="Timestamp when override was executed")


class ETAExperimentResponse(BaseModel):
    """Measurable evaluation metrics comparing simple baseline vs context-aware ETA model."""

    model_config = ConfigDict(from_attributes=True)

    baseline_mae_minutes: float = Field(..., description="Mean Absolute Error of simple distance baseline")
    context_aware_mae_minutes: float = Field(..., description="Mean Absolute Error of Context-Aware ETA model")
    baseline_non_routine_mae: float = Field(..., description="MAE during non-routine conditions (adverse weather, traffic/road closures)")
    context_aware_non_routine_mae: float = Field(..., description="MAE of Context-Aware ETA model during non-routine conditions")
    improvement_percent: float = Field(..., description="Percentage error reduction of Context-Aware model vs baseline")
    sample_count: int = Field(..., description="Number of evaluation samples in benchmark dataset")
    is_simulated_dataset: bool = Field(True, description="Explicit flag identifying dataset source")
    dataset_description: str = Field(..., description="Clear explanation of evaluation benchmark dataset")
    narrative_summary: str = Field(..., description="Human-readable performance comparison narrative")


class ETAResponse(BaseModel):
    """Complete explainable Context-Aware ETA response with optional Dispatcher Override."""

    model_config = ConfigDict(from_attributes=True)

    # ── Job identification ──────────────────────────────────────────────────
    job_id: UUID = Field(..., description="Job identifier")
    job_number: str = Field(..., description="Human-readable job code")

    # ── Context sufficiency ─────────────────────────────────────────────────
    is_context_sufficient: bool = Field(
        ..., description="True if sufficient context existed to compute ETA deterministically"
    )
    calculation_status: str = Field(
        "COMPLETE",
        description="Overall calculation status: COMPLETE | PARTIAL | INSUFFICIENT | ERROR",
    )

    # ── ETA metrics ─────────────────────────────────────────────────────────
    baseline_eta_minutes: Optional[int] = Field(
        None, description="Unobstructed travel time in minutes based on distance / urban speed"
    )
    context_aware_eta_minutes: Optional[int] = Field(
        None, description="Adjusted total ETA in minutes considering all AVAILABLE context factors"
    )
    adjustment_minutes: Optional[int] = Field(
        None, description="Net operational adjustment: context_aware_eta - baseline_eta"
    )
    final_dispatch_eta_minutes: Optional[int] = Field(
        None, description="Final operational ETA (dispatcher override if active, else context_aware_eta)"
    )
    estimated_arrival_time: Optional[str] = Field(
        None, description="Projected wall-clock UTC arrival time (ISO-8601) based on final dispatch ETA"
    )

    # ── Distance ────────────────────────────────────────────────────────────
    distance_miles: Optional[float] = Field(None, description="Haversine transit distance in miles")
    distance_km: Optional[float] = Field(None, description="Haversine transit distance in kilometres")

    # ── Technician ──────────────────────────────────────────────────────────
    technician_id: Optional[UUID] = Field(None, description="Technician evaluated for travel ETA")
    technician_name: Optional[str] = Field(None, description="Technician full name")
    technician_code: Optional[str] = Field(None, description="Technician employee code")

    # ── Dispatcher Override ──────────────────────────────────────────────────
    active_override: Optional[ETAOverrideResponse] = Field(
        None, description="Active dispatcher manual override, if present"
    )

    # ── Context factors & data sources ──────────────────────────────────────
    factors: list[ContextFactor] = Field(
        default_factory=list, description="Breakdown of AVAILABLE context adjustments applied"
    )
    data_sources: list[DataSource] = Field(
        default_factory=list,
        description="All evaluated context data sources with their operational status",
    )

    # ── Explainability ──────────────────────────────────────────────────────
    reason: str = Field(..., description="Primary summary explanation for the ETA and any adjustments")
    missing_context: list[str] = Field(
        default_factory=list, description="Explanations of missing required data if context is insufficient"
    )
    calculated_at: datetime = Field(..., description="UTC calculation timestamp")
