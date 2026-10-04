"""
Pydantic schemas for Context-Aware ETA Engine (Module 11 Upgrade).
Provides structured definitions for factors, data sources, calculation parameters,
dispatcher overrides, experiment performance evaluation, and fully explainable ETA responses.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContextFactor(BaseModel):
    """Specific operational context factor affecting the baseline ETA."""

    model_config = ConfigDict(from_attributes=True)

    category: str = Field(..., description="Factor category: TRAVEL, WEATHER, TRAFFIC, EVENTS, ROAD, GPS, AVAILABILITY")
    factor: str = Field(..., description="Short identifier of the factor")
    impact_minutes: int = Field(..., description="Minutes added or subtracted (+ / -)")
    description: str = Field(..., description="Human-readable explanation of the operational condition")
    provenance: str = Field("DERIVED", description="Provenance of calculated impact: DERIVED for computed operational adjustments")
    is_route_relevant: Optional[bool] = Field(None, description="Whether this factor was determined to be route/corridor-relevant")
    relevance_status: Optional[str] = Field(None, description="Granular route relevance status: RELEVANT | NOT_RELEVANT | ROUTE_ADJACENT | ADVISORY")
    relevance_reason: Optional[str] = Field(None, description="Human-readable explanation of why this factor was or was not applied to ETA")
    applied_to_eta: Optional[bool] = Field(None, description="Whether this factor contributed a positive delay impact to the final Context ETA")
    distance_to_route: Optional[float] = Field(None, description="Shortest distance to selected route polyline in miles")
    distance_to_route_meters: Optional[float] = Field(None, description="Shortest distance to selected route polyline in meters")
    distance_to_route_km: Optional[float] = Field(None, description="Shortest distance to selected route polyline in kilometers")
    distance_to_route_display: Optional[str] = Field(None, description="Human-readable metric distance to route (e.g. '50 m' or '1.2 km')")
    freshness: Optional[str] = Field("UNKNOWN", description="Data freshness state: FRESH | STALE | UNAVAILABLE | UNKNOWN")
    impact_classification: Optional[str] = Field("NOT_APPLIED", description="Causal impact classification: INCLUDED_IN_LIVE_ROUTE | INCREMENTAL_DETOUR | INDEPENDENT_CONTEXT | NOT_APPLIED | UNAVAILABLE")
    provider_timestamp: Optional[str] = Field(None, description="ISO-8601 UTC timestamp reported by upstream provider")
    fetched_timestamp: Optional[str] = Field(None, description="ISO-8601 UTC timestamp when data was fetched by FieldOps AI")
    data_age_seconds: Optional[int] = Field(None, description="Age of data in seconds at calculation time")
    affected_geometry_available: Optional[bool] = Field(None, description="Whether incident provided detailed LineString/MultiLineString geometry")
    alternate_route_available: Optional[bool] = Field(None, description="Whether an alternate route avoiding the restriction could be computed")
    alternate_route_valid: Optional[bool] = Field(None, description="Whether alternate route successfully avoided the closure without re-intersecting")
    original_route_time_seconds: Optional[int] = Field(None, description="Original live route travel time in seconds")
    alternate_route_time_seconds: Optional[int] = Field(None, description="Alternate route live travel time in seconds")
    detour_seconds: Optional[int] = Field(None, description="Measured additional travel time seconds on alternate route")
    incident_delay_seconds: Optional[int] = Field(None, description="TomTom reported incident delay in seconds for non-closure incidents")
    detour_display: Optional[str] = Field(None, description="Human-readable formatted detour evidence (e.g. '13 sec additional (<1 min)' or '1 min 12 sec additional')")
    causal_status: Optional[str] = Field(None, description="Semantic status: NOT_RELEVANT | RELEVANT_NO_ADDITIONAL_DETOUR | RELEVANT_INCREMENTAL_DETOUR | RELEVANT_INCIDENT_DELAY | INCLUDED_IN_LIVE_ROUTE | UNAVAILABLE | STALE")


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
    provenance: str = Field(
        "UNAVAILABLE",
        description=(
            "Data provenance classification: "
            "REAL (live external API), "
            "DERIVED (routing engine / computed), "
            "SYSTEM (internal DB record), "
            "UNAVAILABLE (not configured or unreachable)"
        ),
    )
    freshness: Optional[str] = Field("UNKNOWN", description="Data freshness state: FRESH | STALE | UNAVAILABLE | UNKNOWN")
    impact_classification: Optional[str] = Field("NOT_APPLIED", description="Causal impact classification: INCLUDED_IN_LIVE_ROUTE | INCREMENTAL_DETOUR | INDEPENDENT_CONTEXT | NOT_APPLIED | UNAVAILABLE")
    provider_timestamp: Optional[str] = Field(None, description="ISO-8601 UTC timestamp reported by upstream provider")
    fetched_timestamp: Optional[str] = Field(None, description="ISO-8601 UTC timestamp when data was fetched by FieldOps AI")
    data_age_seconds: Optional[int] = Field(None, description="Age of data in seconds at calculation time")
    corridor_buffer_meters: Optional[float] = Field(None, description="Route corridor relevance buffer in meters (e.g. 50.0 m for point fallback)")
    precipitation_mm: Optional[float] = Field(None, description="Real precipitation amount in mm if available from live feed")
    wind_speed_kmh: Optional[float] = Field(None, description="Real wind speed in km/h if available from live feed")
    wind_direction_deg: Optional[float] = Field(None, description="Real wind direction in degrees if available from live feed")
    temperature_c: Optional[float] = Field(None, description="Real ambient temperature in Celsius if available from live feed")
    condition: Optional[str] = Field(None, description="Human-readable weather condition label")
    event_count: Optional[int] = Field(None, description="Number of active events detected near destination")
    active_event_name: Optional[str] = Field(None, description="Name or title of primary active event")
    event_category: Optional[str] = Field(None, description="Category of active event (e.g. sports, festivals, concerts)")
    event_attendance: Optional[int] = Field(None, description="Predicted attendance from event feed")
    event_rank: Optional[int] = Field(None, description="Rank or impact score from event feed")
    event_id: Optional[str] = Field(None, description="PredictHQ event unique ID")
    event_start: Optional[str] = Field(None, description="Event scheduled start time (ISO 8601 UTC)")
    event_end: Optional[str] = Field(None, description="Event scheduled end time (ISO 8601 UTC)")
    event_latitude: Optional[float] = Field(None, description="Event venue latitude")
    event_longitude: Optional[float] = Field(None, description="Event venue longitude")
    event_location_summary: Optional[str] = Field(None, description="Event venue address or geographic summary")
    event_distance_miles: Optional[float] = Field(None, description="Distance from job destination in miles")
    event_relevance: Optional[float] = Field(None, description="PredictHQ event relevance score")
    restriction_count: Optional[int] = Field(None, description="Number of active road restrictions or incidents on route")
    active_restriction_name: Optional[str] = Field(None, description="Primary road restriction description or road name")
    restriction_category: Optional[str] = Field(None, description="Type or category of incident (e.g., Road Closed, Lane Closed, Jam, Accident)")
    restriction_severity: Optional[str] = Field(None, description="Severity or magnitude of delay (e.g., Major, Moderate, Minor, Blocking)")
    restriction_id: Optional[str] = Field(None, description="TomTom incident unique ID")
    restriction_start: Optional[str] = Field(None, description="Incident start or validity start time (ISO 8601 UTC)")
    restriction_end: Optional[str] = Field(None, description="Incident end or validity end time (ISO 8601 UTC)")
    restriction_road_name: Optional[str] = Field(None, description="Affected road name (from / to)")
    restriction_delay_seconds: Optional[int] = Field(None, description="Incident delay in seconds reported by TomTom")
    restriction_distance_miles: Optional[float] = Field(None, description="Distance of incident from origin or destination in miles")
    is_road_closed: Optional[bool] = Field(None, description="Whether the incident represents a complete road closure")
    is_route_relevant: Optional[bool] = Field(None, description="Whether the incident/event is route/corridor relevant")
    relevance_status: Optional[str] = Field(None, description="Granular route relevance status: RELEVANT | NOT_RELEVANT | ROUTE_ADJACENT | ADVISORY")
    relevance_reason: Optional[str] = Field(None, description="Human-readable explanation of why this factor was or was not applied to ETA")
    applied_to_eta: Optional[bool] = Field(None, description="Whether this factor contributed a positive delay impact to the final Context ETA")
    distance_to_route: Optional[float] = Field(None, description="Shortest distance to selected route polyline in miles")
    distance_to_route_meters: Optional[float] = Field(None, description="Shortest distance to selected route polyline in meters")
    distance_to_route_km: Optional[float] = Field(None, description="Shortest distance to selected route polyline in kilometers")
    distance_to_route_display: Optional[str] = Field(None, description="Human-readable metric distance to route (e.g. '50 m' or '1.2 km')")
    detour_travel_time_minutes: Optional[int] = Field(None, description="Computed detour driving time in minutes")
    evaluated_items: Optional[list[dict]] = Field(None, description="List of individual evaluated items with individual relevance decisions")
    traffic_delay_seconds: Optional[int] = Field(None, description="Traffic delay in seconds reported by routing provider")
    free_flow_eta_minutes: Optional[int] = Field(None, description="Free-flow driving duration without traffic in minutes")
    live_route_eta_minutes: Optional[int] = Field(None, description="Current traffic-aware driving duration in minutes")
    routed_distance_meters: Optional[float] = Field(None, description="Routed road network driving distance in meters")
    routed_distance_miles: Optional[float] = Field(None, description="Routed road network driving distance in miles")
    routed_distance_km: Optional[float] = Field(None, description="Routed road network driving distance in kilometres")
    route_geometry: Optional[list] = Field(None, description="Route polyline coordinates from routing engine")
    affected_geometry_available: Optional[bool] = Field(None, description="Whether incident provided detailed LineString/MultiLineString geometry")
    alternate_route_available: Optional[bool] = Field(None, description="Whether an alternate route avoiding the restriction could be computed")
    alternate_route_valid: Optional[bool] = Field(None, description="Whether alternate route successfully avoided the closure without re-intersecting")
    original_route_time_seconds: Optional[int] = Field(None, description="Original live route travel time in seconds")
    alternate_route_time_seconds: Optional[int] = Field(None, description="Alternate route live travel time in seconds")
    detour_seconds: Optional[int] = Field(None, description="Measured additional travel time seconds on alternate route")
    incident_delay_seconds: Optional[int] = Field(None, description="TomTom reported incident delay in seconds for non-closure incidents")
    detour_display: Optional[str] = Field(None, description="Human-readable formatted detour evidence (e.g. '13 sec additional (<1 min)' or '1 min 12 sec additional')")
    causal_status: Optional[str] = Field(None, description="Semantic status: NOT_RELEVANT | RELEVANT_NO_ADDITIONAL_DETOUR | RELEVANT_INCREMENTAL_DETOUR | RELEVANT_INCIDENT_DELAY | INCLUDED_IN_LIVE_ROUTE | UNAVAILABLE | STALE")


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


class ETAExperimentSampleResult(BaseModel):
    """Detailed evaluation calculation for a single evaluation scenario sample."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Scenario sample identifier")
    distance_km: float = Field(..., description="Transit distance in kilometres")
    baseline_eta_minutes: int = Field(..., description="Simple distance baseline travel ETA in minutes")
    context_aware_eta_minutes: int = Field(..., description="Context-Aware model travel ETA in minutes")
    actual_travel_minutes: float = Field(..., description="Observed / actual travel duration in minutes")
    baseline_absolute_error: float = Field(..., description="Absolute prediction error of baseline (|Baseline - Actual|)")
    context_aware_absolute_error: float = Field(..., description="Absolute prediction error of Context-Aware model (|Context - Actual|)")
    improvement_minutes: float = Field(..., description="Prediction error reduction in minutes (Baseline Error - Context Error)")
    is_non_routine: bool = Field(..., description="True if scenario features adverse environmental / transit conditions")
    conditions: str = Field(..., description="Summary of environmental factors present during transit")


class ETAExperimentResponse(BaseModel):
    """Measurable evaluation metrics comparing simple baseline vs context-aware ETA model."""

    model_config = ConfigDict(from_attributes=True)

    baseline_mae_minutes: Optional[float] = Field(None, description="Mean Absolute Error of simple distance baseline")
    context_aware_mae_minutes: Optional[float] = Field(None, description="Mean Absolute Error of Context-Aware ETA model")
    baseline_routine_mae: Optional[float] = Field(None, description="Baseline MAE during routine (normal) transit conditions")
    context_aware_routine_mae: Optional[float] = Field(None, description="Context-Aware MAE during routine (normal) transit conditions")
    baseline_non_routine_mae: Optional[float] = Field(None, description="MAE during non-routine conditions (adverse weather, traffic/road closures)")
    context_aware_non_routine_mae: Optional[float] = Field(None, description="MAE of Context-Aware ETA model during non-routine conditions")
    improvement_percent: Optional[float] = Field(None, description="Overall percentage error reduction of Context-Aware model vs baseline")
    non_routine_improvement_percent: Optional[float] = Field(None, description="Percentage error reduction during non-routine conditions")
    sample_count: int = Field(0, description="Number of evaluation samples in benchmark dataset")
    routine_sample_count: int = Field(0, description="Number of routine scenario samples evaluated")
    non_routine_sample_count: int = Field(0, description="Number of non-routine scenario samples evaluated")
    is_simulated_dataset: bool = Field(False, description="Explicit flag identifying dataset source")
    is_sufficient_data: bool = Field(False, description="True if sufficient real operational telemetry exists")
    min_required_samples: int = Field(10, description="Minimum samples required for statistical significance")
    dataset_description: str = Field(..., description="Clear explanation of evaluation benchmark dataset")
    narrative_summary: str = Field(..., description="Human-readable performance comparison narrative")
    disclaimer: str = Field("Simulated evaluation — not real-world historical validation.", description="Explicit transparency disclaimer")
    sample_breakdown: list[ETAExperimentSampleResult] = Field(default_factory=list, description="Sample-by-sample detailed evaluation calculations")
    error_analysis: list[dict[str, str]] = Field(default_factory=list, description="Categorized operational insights explaining model performance")


class ETAResponse(BaseModel):
    """Complete explainable Context-Aware ETA response with optional Dispatcher Override."""

    model_config = ConfigDict(from_attributes=True)

    # ── Job identification ──────────────────────────────────────────────────
    job_id: UUID = Field(..., description="Job identifier")
    job_number: str = Field(..., description="Human-readable job code")

    # ── Context sufficiency & Operational Realism ───────────────────────────
    is_context_sufficient: bool = Field(
        ..., description="True if sufficient context existed to compute ETA deterministically"
    )
    calculation_status: str = Field(
        "COMPLETE",
        description="Overall calculation status: COMPLETE | PARTIAL | INSUFFICIENT | ERROR",
    )
    is_operationally_realistic: bool = Field(
        default=True,
        description="False if route exceeds practical field service dispatch territory (e.g. cross-continental)",
    )
    route_validity: str = Field(
        default="VALID",
        description="Route operational validity: VALID | OUT_OF_SERVICE_AREA | UNROUTEABLE",
    )
    service_range_message: Optional[str] = Field(
        default=None,
        description="Operational explanation when route is outside practical service territory",
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

    # ── Distance & Routing Telemetry ─────────────────────────────────────────
    distance_miles: Optional[float] = Field(None, description="Transit distance in miles (routed road distance if available, else Haversine)")
    distance_km: Optional[float] = Field(None, description="Transit distance in kilometres (routed road distance if available, else Haversine)")
    routed_distance_miles: Optional[float] = Field(None, description="Actual road network driving distance in miles from routing provider")
    routed_distance_km: Optional[float] = Field(None, description="Actual road network driving distance in kilometres from routing provider")
    haversine_distance_miles: Optional[float] = Field(None, description="Straight-line Haversine distance in miles")
    haversine_distance_km: Optional[float] = Field(None, description="Straight-line Haversine distance in kilometres")
    traffic_delay_minutes: Optional[int] = Field(None, description="Traffic delay in minutes reported by routing provider")
    route_geometry: Optional[list] = Field(None, description="Route polyline coordinates from routing engine")
    route_provenance: str = Field("DERIVED", description="Provenance of route calculation: REAL (TomTom live routing), DERIVED (OSRM / fallback)")
    free_flow_eta_minutes: Optional[int] = Field(None, description="Free-flow driving duration without traffic in minutes")
    live_route_eta_minutes: Optional[int] = Field(None, description="Current traffic-aware driving duration in minutes")
    additional_verified_impact_minutes: Optional[int] = Field(0, description="Additional verified incremental ETA delay beyond live route travel time")
    routed_distance_meters: Optional[float] = Field(None, description="Actual road network driving distance in meters from routing provider")

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

    # ── Confidence & Source Reliability (Phase 4G) ───────────────────────────
    confidence_level: str = Field(
        default="HIGH",
        description="Categorical ETA reliability: HIGH | MEDIUM | LOW | DEGRADED | UNAVAILABLE",
    )
    confidence_reason: str = Field(
        default="Authoritative route and verified telemetry available.",
        description="Deterministic, transparent explanation of reliability and degradation causes",
    )
    reliability_status: str = Field(
        default="HIGH",
        description="Operational reliability status matching confidence_level",
    )
    degraded_sources: list[str] = Field(
        default_factory=list,
        description="Sources operating in derived/fallback mode",
    )
    fresh_sources: list[str] = Field(
        default_factory=list,
        description="Sources verified fresh with current telemetry",
    )
    stale_sources: list[str] = Field(
        default_factory=list,
        description="Sources with stale telemetry exceeding threshold",
    )
    unavailable_sources: list[str] = Field(
        default_factory=list,
        description="Optional or required sources that are unreachable",
    )

    # ── Compatibility Aliases ───────────────────────────────────────────────
    baseline_travel_time_minutes: Optional[int] = Field(
        None, description="Alias for baseline_eta_minutes for contract compatibility"
    )
    data_source_statuses: Optional[list[DataSource]] = Field(
        default=None, description="Alias for data_sources for contract compatibility"
    )

    @model_validator(mode="after")
    def populate_compatibility_aliases(self) -> "ETAResponse":
        if self.baseline_travel_time_minutes is None:
            self.baseline_travel_time_minutes = self.baseline_eta_minutes
        elif self.baseline_eta_minutes is None:
            self.baseline_eta_minutes = self.baseline_travel_time_minutes

        if self.data_source_statuses is None and self.data_sources:
            self.data_source_statuses = list(self.data_sources)
        elif not self.data_sources and self.data_source_statuses:
            self.data_sources = list(self.data_source_statuses)
        return self
