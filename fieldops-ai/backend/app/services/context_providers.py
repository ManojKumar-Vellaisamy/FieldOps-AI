"""
Context Provider Architecture for Module 10 — Context-Aware ETA Engine.

Each provider encapsulates a distinct operational data source that affects travel-time estimation.
Providers return an explicit ContextProviderResult that includes:
  - status (AVAILABLE | STALE | UNAVAILABLE | INVALID)
  - impact_minutes (0 when unavailable or no delay)
  - description (human-readable explanation)
  - sampled_at (UTC timestamp of when context was sampled)
  - source_name (label for the data source)

Providers DO NOT invent, fake, or interpolate missing data.
When a source is not available the provider returns UNAVAILABLE with 0 impact.

Currently AVAILABLE sources:
  - GPSLocationProvider  — reads from Technician.current_latitude/longitude in PostgreSQL
  - WeatherProvider      — uses dispatcher-supplied ?weather= query param or system default

Currently UNAVAILABLE sources (architecture ready for future ingestion):
  - TrafficDataProvider       — no real-time traffic feed integrated
  - EventsDataProvider        — no event/permit data feed integrated
  - RoadRestrictionProvider   — no road-closure/restriction feed integrated
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Data Source Status Enum ────────────────────────────────────────────────────

class DataSourceStatus(str, Enum):
    """Operational status of a context data source."""

    AVAILABLE = "AVAILABLE"
    """Data was successfully retrieved and is current."""

    STALE = "STALE"
    """Data exists but was captured beyond the acceptable freshness threshold."""

    UNAVAILABLE = "UNAVAILABLE"
    """Source is not integrated or currently unreachable; no impact applied."""

    INVALID = "INVALID"
    """Data was received but failed validation (e.g. out-of-range coordinates)."""


# ── Provider Result ────────────────────────────────────────────────────────────

# ── Metric Unit Standardization Helpers ────────────────────────────────────────

def _miles_to_meters(miles: float) -> float:
    """Convert miles to meters."""
    return round(miles * 1609.344, 1)


def _meters_to_miles(meters: float) -> float:
    """Convert meters to miles."""
    return round(meters / 1609.344, 4)


def _format_metric_distance(meters: Optional[float]) -> str:
    """Format metric distance for human-readable logs and UI (e.g. '50 m' or '1.25 km')."""
    if meters is None or meters == float("inf"):
        return "—"
    if meters < 1000.0:
        return f"{round(meters)} m"
    return f"{meters / 1000.0:.2f} km"


@dataclass
class ContextProviderResult:
    """
    Structured result returned by every context provider.
    When status is not AVAILABLE, impact_minutes must be 0.
    """

    source_name: str
    """Human-readable label for this data source."""

    status: DataSourceStatus
    """Operational status of the data retrieved."""

    impact_minutes: int
    """ETA adjustment in minutes. Must be 0 if status != AVAILABLE."""

    description: str
    """Operational explanation suitable for the dispatcher UI."""

    sampled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """UTC timestamp when this context was evaluated."""

    category: str = "UNKNOWN"
    """Factor category for UI grouping (TRAVEL, WEATHER, TRAFFIC, EVENTS, ROAD)."""

    provenance: str = "UNAVAILABLE"
    """
    Data provenance classification for UI display:
      REAL        — live external API data successfully received (Open-Meteo, TomTom with key)
      DERIVED     — computed / synthesised from routing engine (OSRM, haversine baseline)
      SYSTEM      — sourced from internal system records (GPS from DB)
      UNAVAILABLE — source not configured, unreachable, or returned invalid data
    """

    freshness: str = "UNKNOWN"
    """
    Data freshness state:
      FRESH       — data timestamp is current and within operational freshness limits
      STALE       — data exists but was captured beyond acceptable operational threshold
      UNAVAILABLE — source data could not be retrieved
      UNKNOWN     — provider does not expose a reliable observation timestamp
    """

    impact_classification: str = "NOT_APPLIED"
    """
    Causal impact classification:
      INCLUDED_IN_LIVE_ROUTE — slowdown already reflected in authoritative live route travel time
      INCREMENTAL_DETOUR     — independently verified detour duration above live route
      INDEPENDENT_CONTEXT    — independently verified environmental context (e.g. severe weather)
      NOT_APPLIED            — factor detected/evaluated but produced 0 ETA impact
      UNAVAILABLE            — provider unavailable or evaluation failed
    """

    provider_timestamp: Optional[str] = None
    """ISO-8601 UTC timestamp reported directly by the external provider."""

    fetched_timestamp: Optional[str] = None
    """ISO-8601 UTC timestamp when FieldOps AI queried or fetched this context."""

    data_age_seconds: Optional[int] = None
    """Data age in seconds at time of evaluation."""

    corridor_buffer_meters: Optional[float] = None
    """Route corridor relevance buffer in meters (e.g. 50.0 m for point fallback)."""

    distance_to_route_meters: Optional[float] = None
    """Shortest perpendicular distance from incident or event to route in meters."""

    distance_to_route_km: Optional[float] = None
    """Shortest perpendicular distance from incident or event to route in kilometers."""

    distance_to_route_display: Optional[str] = None
    """Human-readable metric distance string (e.g. '50 m' or '1.2 km')."""

    precipitation_mm: Optional[float] = None
    """Real precipitation in mm if available from live provider feed."""

    wind_speed_kmh: Optional[float] = None
    """Real wind speed in km/h if available from live provider feed."""

    wind_direction_deg: Optional[float] = None
    """Real wind direction in degrees if available from live provider feed."""

    temperature_c: Optional[float] = None
    """Real ambient temperature in Celsius if available from live provider feed."""

    apparent_temperature_c: Optional[float] = None
    """Real apparent/feels-like temperature in Celsius from live provider feed."""

    humidity_percent: Optional[float] = None
    """Real relative humidity percentage (0-100) from live provider feed."""

    precipitation_probability_percent: Optional[float] = None
    """Forecast precipitation probability percentage (0-100) from live provider feed."""

    condition: Optional[str] = None
    """Human-readable weather condition label (e.g. Overcast, Clear sky)."""

    event_count: Optional[int] = None
    """Number of active events detected near destination."""

    active_event_name: Optional[str] = None
    """Primary active event title/name."""

    event_category: Optional[str] = None
    """Primary event category."""

    event_attendance: Optional[int] = None
    """Predicted attendance from event feed."""

    event_rank: Optional[int] = None
    """Rank or impact score from event feed."""

    event_id: Optional[str] = None
    """PredictHQ event unique ID."""

    event_start: Optional[str] = None
    """Event scheduled start time (ISO 8601 UTC)."""

    event_end: Optional[str] = None
    """Event scheduled end time (ISO 8601 UTC)."""

    event_latitude: Optional[float] = None
    """Event venue latitude."""

    event_longitude: Optional[float] = None
    """Event venue longitude."""

    event_location_summary: Optional[str] = None
    """Event venue address or geographic summary."""

    event_distance_miles: Optional[float] = None
    """Distance from job destination in miles."""

    event_relevance: Optional[float] = None
    """PredictHQ event relevance score."""

    restriction_count: Optional[int] = None
    """Number of active road restrictions or incidents on route."""

    active_restriction_name: Optional[str] = None
    """Primary road restriction description or road name."""

    restriction_category: Optional[str] = None
    """Type or category of incident (Road Closed, Lane Closed, Jam, Accident, etc.)."""

    restriction_severity: Optional[str] = None
    """Severity or magnitude of delay (Major, Moderate, Minor, Blocking, etc.)."""

    restriction_id: Optional[str] = None
    """TomTom incident unique ID."""

    restriction_start: Optional[str] = None
    """Incident start or validity start time (ISO 8601 UTC)."""

    restriction_end: Optional[str] = None
    """Incident end or validity end time (ISO 8601 UTC)."""

    restriction_road_name: Optional[str] = None
    """Affected road name (from / to)."""

    restriction_delay_seconds: Optional[int] = None
    """Incident delay in seconds reported by TomTom."""

    restriction_distance_miles: Optional[float] = None
    """Distance of incident from origin or destination in miles."""

    is_road_closed: Optional[bool] = None
    """Whether the incident represents a complete road closure."""

    is_route_relevant: Optional[bool] = None
    """Whether this factor was verified to be route/corridor-relevant."""

    route_geometry: Optional[list] = None
    """Route polyline coordinates from routing engine if available."""

    free_flow_travel_time_seconds: Optional[int] = None
    """Free-flow driving route duration in seconds from routing engine."""

    live_travel_time_seconds: Optional[int] = None
    """Traffic-aware driving route duration in seconds from routing engine."""

    traffic_delay_seconds: Optional[int] = None
    """Traffic delay in seconds compared to free-flow from routing engine."""

    routed_distance_meters: Optional[float] = None
    """Road network route distance in meters from routing engine."""

    routed_distance_miles: Optional[float] = None
    """Road network route distance in miles from routing engine."""

    routed_distance_km: Optional[float] = None
    """Road network route distance in kilometres from routing engine."""

    relevance_status: Optional[str] = None
    """Granular route relevance status: RELEVANT | NOT_RELEVANT | ROUTE_ADJACENT | ADVISORY."""

    relevance_reason: Optional[str] = None
    """Human-readable explanation of why this factor was or was not applied to ETA."""

    applied_to_eta: Optional[bool] = None
    """Whether this factor contributed a positive delay impact to the final Context ETA."""

    distance_to_route: Optional[float] = None
    """Shortest perpendicular distance from the incident or event to the selected route polyline in miles."""

    detour_travel_time_minutes: Optional[int] = None
    """Computed detour driving time in minutes when route-avoidance routing is performed."""

    evaluated_items: Optional[list[dict]] = None
    """List of individual parsed incidents or events with individual relevance decisions."""

    affected_geometry_available: Optional[bool] = None
    """Whether incident provided detailed LineString/MultiLineString geometry."""

    alternate_route_available: Optional[bool] = None
    """Whether an alternate route avoiding the restriction could be computed."""

    alternate_route_valid: Optional[bool] = None
    """Whether alternate route successfully avoided the closure without re-intersecting."""

    original_route_time_seconds: Optional[int] = None
    """Original live route travel time in seconds."""

    alternate_route_time_seconds: Optional[int] = None
    """Alternate route live travel time in seconds."""

    detour_seconds: Optional[int] = None
    """Measured additional travel time seconds on alternate route."""

    incident_delay_seconds: Optional[int] = None
    """Incident delay in seconds reported directly by upstream provider (e.g. TomTom properties.delay)."""

    detour_display: Optional[str] = None
    """Human-readable formatted detour evidence (e.g. '13 sec additional (<1 min)' or '1 min 12 sec additional')."""

    causal_status: Optional[str] = None
    """Semantic status: NOT_RELEVANT | RELEVANT_NO_ADDITIONAL_DETOUR | RELEVANT_INCREMENTAL_DETOUR | RELEVANT_INCIDENT_DELAY | INCLUDED_IN_LIVE_ROUTE | UNAVAILABLE | STALE."""

    def to_factor_dict(self) -> dict:
        """Convert to ContextFactor-compatible dict for ETA response."""
        d = {
            "category": self.category,
            "factor": self.source_name,
            "impact_minutes": self.impact_minutes,
            "description": self.description,
            "provenance": "DERIVED" if self.provenance == "REAL" and self.impact_minutes > 0 else (self.provenance if self.provenance != "UNAVAILABLE" else "DERIVED"),
            "freshness": self.freshness,
            "impact_classification": self.impact_classification,
        }
        if self.provider_timestamp is not None:
            d["provider_timestamp"] = self.provider_timestamp
        if self.fetched_timestamp is not None:
            d["fetched_timestamp"] = self.fetched_timestamp
        if self.data_age_seconds is not None:
            d["data_age_seconds"] = self.data_age_seconds
        if self.is_route_relevant is not None:
            d["is_route_relevant"] = self.is_route_relevant
        if self.relevance_status is not None:
            d["relevance_status"] = self.relevance_status
        if self.relevance_reason is not None:
            d["relevance_reason"] = self.relevance_reason
        if self.applied_to_eta is not None:
            d["applied_to_eta"] = self.applied_to_eta
        if self.distance_to_route is not None:
            d["distance_to_route"] = self.distance_to_route
            d["distance_to_route_meters"] = self.distance_to_route_meters or _miles_to_meters(self.distance_to_route)
            d["distance_to_route_km"] = self.distance_to_route_km or round((self.distance_to_route_meters or _miles_to_meters(self.distance_to_route)) / 1000.0, 3)
            d["distance_to_route_display"] = self.distance_to_route_display or _format_metric_distance(d["distance_to_route_meters"])
        if self.category == "ROAD":
            d["affected_geometry_available"] = self.affected_geometry_available
            d["alternate_route_available"] = self.alternate_route_available
            d["alternate_route_valid"] = self.alternate_route_valid
            d["original_route_time_seconds"] = self.original_route_time_seconds
            d["alternate_route_time_seconds"] = self.alternate_route_time_seconds
            d["detour_seconds"] = self.detour_seconds
            d["incident_delay_seconds"] = self.incident_delay_seconds
            d["detour_display"] = self.detour_display
            d["causal_status"] = self.causal_status
        else:
            if self.affected_geometry_available is not None:
                d["affected_geometry_available"] = self.affected_geometry_available
            if self.alternate_route_available is not None:
                d["alternate_route_available"] = self.alternate_route_available
            if self.alternate_route_valid is not None:
                d["alternate_route_valid"] = self.alternate_route_valid
            if self.original_route_time_seconds is not None:
                d["original_route_time_seconds"] = self.original_route_time_seconds
            if self.alternate_route_time_seconds is not None:
                d["alternate_route_time_seconds"] = self.alternate_route_time_seconds
            if self.detour_seconds is not None:
                d["detour_seconds"] = self.detour_seconds
            if self.incident_delay_seconds is not None:
                d["incident_delay_seconds"] = self.incident_delay_seconds
            if self.detour_display is not None:
                d["detour_display"] = self.detour_display
            if self.causal_status is not None:
                d["causal_status"] = self.causal_status
        return d

    def to_data_source_dict(self) -> dict:
        """Convert to DataSource-compatible dict for ETA response."""
        d = {
            "name": self.source_name,
            "status": self.status.value,
            "description": self.description,
            "impact_minutes": self.impact_minutes,
            "sampled_at": self.sampled_at.isoformat(),
            "category": self.category,
            "provenance": self.provenance,
            "freshness": self.freshness,
            "impact_classification": self.impact_classification,
        }
        if self.provider_timestamp is not None:
            d["provider_timestamp"] = self.provider_timestamp
        if self.fetched_timestamp is not None:
            d["fetched_timestamp"] = self.fetched_timestamp
        if self.data_age_seconds is not None:
            d["data_age_seconds"] = self.data_age_seconds
        if self.corridor_buffer_meters is not None:
            d["corridor_buffer_meters"] = self.corridor_buffer_meters
        if self.is_route_relevant is not None:
            d["is_route_relevant"] = self.is_route_relevant
        if self.relevance_status is not None:
            d["relevance_status"] = self.relevance_status
        if self.relevance_reason is not None:
            d["relevance_reason"] = self.relevance_reason
        if self.applied_to_eta is not None:
            d["applied_to_eta"] = self.applied_to_eta
        if self.distance_to_route is not None:
            d["distance_to_route"] = self.distance_to_route
            d["distance_to_route_meters"] = self.distance_to_route_meters or _miles_to_meters(self.distance_to_route)
            d["distance_to_route_km"] = self.distance_to_route_km or round((self.distance_to_route_meters or _miles_to_meters(self.distance_to_route)) / 1000.0, 3)
            d["distance_to_route_display"] = self.distance_to_route_display or _format_metric_distance(d["distance_to_route_meters"])
        if self.routed_distance_meters is not None:
            d["routed_distance_meters"] = self.routed_distance_meters
        if self.detour_travel_time_minutes is not None:
            d["detour_travel_time_minutes"] = self.detour_travel_time_minutes
        if self.evaluated_items is not None:
            d["evaluated_items"] = self.evaluated_items
        if self.precipitation_mm is not None:
            d["precipitation_mm"] = self.precipitation_mm
        if self.wind_speed_kmh is not None:
            d["wind_speed_kmh"] = self.wind_speed_kmh
        if self.wind_direction_deg is not None:
            d["wind_direction_deg"] = self.wind_direction_deg
        if self.apparent_temperature_c is not None:
            d["apparent_temperature_c"] = self.apparent_temperature_c
        if self.humidity_percent is not None:
            d["humidity_percent"] = self.humidity_percent
        if self.precipitation_probability_percent is not None:
            d["precipitation_probability_percent"] = self.precipitation_probability_percent
        if self.event_count is not None:
            d["event_count"] = self.event_count
        if self.active_event_name is not None:
            d["active_event_name"] = self.active_event_name
        if self.event_category is not None:
            d["event_category"] = self.event_category
        if self.event_attendance is not None:
            d["event_attendance"] = self.event_attendance
        if self.event_rank is not None:
            d["event_rank"] = self.event_rank
        if self.event_id is not None:
            d["event_id"] = self.event_id
        if self.event_start is not None:
            d["event_start"] = self.event_start
        if self.event_end is not None:
            d["event_end"] = self.event_end
        if self.event_latitude is not None:
            d["event_latitude"] = self.event_latitude
        if self.event_longitude is not None:
            d["event_longitude"] = self.event_longitude
        if self.event_location_summary is not None:
            d["event_location_summary"] = self.event_location_summary
        if self.event_distance_miles is not None:
            d["event_distance_miles"] = self.event_distance_miles
        if self.event_relevance is not None:
            d["event_relevance"] = self.event_relevance
        if self.restriction_count is not None:
            d["restriction_count"] = self.restriction_count
        if self.active_restriction_name is not None:
            d["active_restriction_name"] = self.active_restriction_name
        if self.restriction_category is not None:
            d["restriction_category"] = self.restriction_category
        if self.restriction_severity is not None:
            d["restriction_severity"] = self.restriction_severity
        if self.restriction_id is not None:
            d["restriction_id"] = self.restriction_id
        if self.restriction_start is not None:
            d["restriction_start"] = self.restriction_start
        if self.restriction_end is not None:
            d["restriction_end"] = self.restriction_end
        if self.restriction_road_name is not None:
            d["restriction_road_name"] = self.restriction_road_name
        if self.restriction_delay_seconds is not None:
            d["restriction_delay_seconds"] = self.restriction_delay_seconds
        if self.restriction_distance_miles is not None:
            d["restriction_distance_miles"] = self.restriction_distance_miles
        if self.is_road_closed is not None:
            d["is_road_closed"] = self.is_road_closed
        if self.temperature_c is not None:
            d["temperature_c"] = self.temperature_c
        if self.condition is not None:
            d["condition"] = self.condition
        if self.traffic_delay_seconds is not None:
            d["traffic_delay_seconds"] = self.traffic_delay_seconds
        if self.free_flow_travel_time_seconds is not None:
            d["free_flow_eta_minutes"] = max(1, round(self.free_flow_travel_time_seconds / 60.0))
        if self.live_travel_time_seconds is not None:
            d["live_route_eta_minutes"] = max(1, round(self.live_travel_time_seconds / 60.0))
        if self.routed_distance_miles is not None:
            d["routed_distance_miles"] = self.routed_distance_miles
        if self.routed_distance_km is not None:
            d["routed_distance_km"] = self.routed_distance_km
        if self.route_geometry is not None:
            d["route_geometry"] = self.route_geometry
        if self.category == "ROAD":
            d["affected_geometry_available"] = self.affected_geometry_available
            d["alternate_route_available"] = self.alternate_route_available
            d["alternate_route_valid"] = self.alternate_route_valid
            d["original_route_time_seconds"] = self.original_route_time_seconds
            d["alternate_route_time_seconds"] = self.alternate_route_time_seconds
            d["detour_seconds"] = self.detour_seconds
            d["incident_delay_seconds"] = self.incident_delay_seconds
            d["detour_display"] = self.detour_display
            d["causal_status"] = self.causal_status
        else:
            if self.affected_geometry_available is not None:
                d["affected_geometry_available"] = self.affected_geometry_available
            if self.alternate_route_available is not None:
                d["alternate_route_available"] = self.alternate_route_available
            if self.alternate_route_valid is not None:
                d["alternate_route_valid"] = self.alternate_route_valid
            if self.original_route_time_seconds is not None:
                d["original_route_time_seconds"] = self.original_route_time_seconds
            if self.alternate_route_time_seconds is not None:
                d["alternate_route_time_seconds"] = self.alternate_route_time_seconds
            if self.detour_seconds is not None:
                d["detour_seconds"] = self.detour_seconds
            if self.incident_delay_seconds is not None:
                d["incident_delay_seconds"] = self.incident_delay_seconds
            if self.detour_display is not None:
                d["detour_display"] = self.detour_display
            if self.causal_status is not None:
                d["causal_status"] = self.causal_status
        return d


# ── Abstract Base Provider ─────────────────────────────────────────────────────

class BaseContextProvider(ABC):
    """Abstract interface that all context providers must implement."""

    @abstractmethod
    async def evaluate(self, **kwargs) -> ContextProviderResult:
        """
        Evaluate this context source and return a ContextProviderResult.
        Implementations must never block on network calls without a timeout.
        """
        ...


# ── GPS Location Provider ──────────────────────────────────────────────────────

# Coordinate validity bounds
_LAT_MIN, _LAT_MAX = -90.0, 90.0
_LON_MIN, _LON_MAX = -180.0, 180.0

# GPS staleness threshold in seconds (10 minutes per Phase 3 spec)
_GPS_STALE_SECONDS = 600


class GPSLocationProvider(BaseContextProvider):
    """
    Evaluates technician GPS location data from PostgreSQL.

    Status rules:
      AVAILABLE  — coordinates exist and pass validation
      STALE      — coordinates exist but technician record updated > 2 h ago
                   (requires technician.updated_at; falls back to AVAILABLE if
                    updated_at is unavailable — a known limitation noted in docs)
      UNAVAILABLE — no coordinates stored for technician
      INVALID     — coordinates exist but are outside valid WGS84 bounds
    """

    async def evaluate(
        self,
        technician_lat: Optional[float] = None,
        technician_lon: Optional[float] = None,
        tech_updated_at: Optional[datetime] = None,
        **kwargs,
    ) -> ContextProviderResult:
        now = datetime.now(timezone.utc)

        now_iso = now.isoformat()
        if technician_lat is None or technician_lon is None:
            return ContextProviderResult(
                source_name="GPS Location",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description="Technician GPS coordinates not available in system.",
                sampled_at=now,
                category="GPS",
                provenance="UNAVAILABLE",
                freshness="UNAVAILABLE",
                impact_classification="UNAVAILABLE",
                fetched_timestamp=now_iso,
            )

        # Validate WGS84 bounds
        if not (_LAT_MIN <= technician_lat <= _LAT_MAX and _LON_MIN <= technician_lon <= _LON_MAX):
            return ContextProviderResult(
                source_name="GPS Location",
                status=DataSourceStatus.INVALID,
                impact_minutes=0,
                description=(
                    f"Technician GPS coordinates ({technician_lat:.4f}, {technician_lon:.4f}) "
                    "are outside valid WGS84 bounds — location fix rejected."
                ),
                sampled_at=now,
                category="GPS",
                provenance="UNAVAILABLE",
                freshness="UNAVAILABLE",
                impact_classification="UNAVAILABLE",
                fetched_timestamp=now_iso,
            )

        # Check staleness if technician location observation timestamp is available
        provider_ts_str = None
        data_age_sec = None
        if tech_updated_at is not None and isinstance(tech_updated_at, datetime):
            # Ensure timezone-aware comparison
            ref = tech_updated_at if tech_updated_at.tzinfo else tech_updated_at.replace(tzinfo=timezone.utc)
            data_age_sec = int((now - ref).total_seconds())
            provider_ts_str = ref.isoformat()
            if data_age_sec > _GPS_STALE_SECONDS:
                return ContextProviderResult(
                    source_name="GPS Location",
                    status=DataSourceStatus.STALE,
                    impact_minutes=0,
                    description=(
                        f"Technician GPS last updated {int(data_age_sec / 60)} min ago — "
                        "location may not reflect current position. ETA computed from last known GPS fix."
                    ),
                    sampled_at=now,
                    category="GPS",
                    provenance="SYSTEM",
                    freshness="STALE",
                    impact_classification="NOT_APPLIED",
                    provider_timestamp=provider_ts_str,
                    fetched_timestamp=now_iso,
                    data_age_seconds=data_age_sec,
                )

        lat_dir = "N" if technician_lat >= 0 else "S"
        lon_dir = "E" if technician_lon >= 0 else "W"

        if tech_updated_at is None or not isinstance(tech_updated_at, datetime):
            freshness_val = "UNKNOWN"
            desc = (
                f"Technician GPS location confirmed ({abs(technician_lat):.4f}° {lat_dir}, {abs(technician_lon):.4f}° {lon_dir}). "
                "GPS observation timestamp unavailable — freshness is UNKNOWN."
            )
        else:
            freshness_val = "FRESH"
            desc = (
                f"Technician GPS location confirmed ({abs(technician_lat):.4f}° {lat_dir}, {abs(technician_lon):.4f}° {lon_dir})."
            )

        return ContextProviderResult(
            source_name="GPS Location",
            status=DataSourceStatus.AVAILABLE,
            impact_minutes=0,
            description=desc,
            sampled_at=now,
            category="GPS",
            provenance="SYSTEM",
            freshness=freshness_val,
            impact_classification="NOT_APPLIED",
            provider_timestamp=provider_ts_str,
            fetched_timestamp=now_iso,
            data_age_seconds=data_age_sec,
        )


# ── Weather Provider ────────────────────────────────────────────────────────────

# Weather condition → ETA adjustment minutes
_WEATHER_IMPACT: dict[str, int] = {
    "CLEAR": 0,
    "FAIR": 0,
    "CLOUDY": 0,
    "MODERATE RAIN": 5,
    "HEAVY RAIN": 12,
    "STORM": 15,
    "THUNDERSTORM": 15,
    "SNOW": 20,
    "BLIZZARD": 30,
    "FOG": 8,
    "ICE": 18,
}

# WMO Weathercode → (Condition Label, Base Impact Minutes)
_WMO_WEATHER_MAP: dict[int, tuple[str, int]] = {
    0: ("Clear sky", 0),
    1: ("Mainly clear", 0),
    2: ("Partly cloudy", 0),
    3: ("Overcast", 0),
    45: ("Fog", 8),
    48: ("Depositing rime fog", 8),
    51: ("Light drizzle", 3),
    53: ("Moderate drizzle", 4),
    55: ("Dense drizzle", 5),
    61: ("Slight rain", 5),
    63: ("Moderate rain", 10),
    65: ("Heavy rain", 15),
    71: ("Slight snow", 15),
    73: ("Moderate snow", 20),
    75: ("Heavy snow", 25),
    80: ("Slight rain showers", 6),
    81: ("Moderate rain showers", 9),
    82: ("Violent rain showers", 14),
    95: ("Thunderstorm", 15),
    96: ("Thunderstorm with slight hail", 18),
    99: ("Thunderstorm with heavy hail", 22),
}

# Default weather used when no live API data or condition is supplied
_DEFAULT_WEATHER = "Clear"


class WeatherProvider(BaseContextProvider):
    """
    Production Real-Time Weather Data Provider.

    Attempts to query Open-Meteo Live Weather API using job coordinates (no API key required).
    If coordinates are unavailable or network call times out/fails, falls back gracefully
    to dispatcher-supplied weather condition parameter or conservative system default.

    Status:
      AVAILABLE   — Real Open-Meteo API response obtained or dispatcher weather supplied.
      UNAVAILABLE — Coords missing and no condition supplied; baseline preserved.
    """

    # In-memory TTL cache: (round(lat, 2), round(lon, 2)) -> (cached_epoch, ContextProviderResult)
    _cache: dict[tuple[float, float], tuple[float, ContextProviderResult]] = {}
    _CACHE_TTL_SECONDS: float = 600.0  # 10 minutes cache

    @classmethod
    def clear_cache(cls) -> None:
        """Clear weather in-memory cache (useful for testing or manual reset)."""
        cls._cache.clear()

    async def evaluate(
        self,
        weather_condition: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        dest_lat: Optional[float] = None,
        dest_lon: Optional[float] = None,
        baseline_eta_minutes: Optional[int] = None,
        distance_miles: Optional[float] = None,
        **kwargs,
    ) -> ContextProviderResult:
        from app.services.settings_service import get_cached_settings_snapshot

        now = datetime.now(timezone.utc)
        sys_settings = get_cached_settings_snapshot()
        weight = sys_settings.weather_delay_weight

        target_lat = lat if lat is not None else dest_lat
        target_lon = lon if lon is not None else dest_lon

        cache_key: Optional[tuple[float, float]] = None
        if target_lat is not None and target_lon is not None and weather_condition is None:
            if -90.0 <= target_lat <= 90.0 and -180.0 <= target_lon <= 180.0:
                cache_key = (round(float(target_lat), 2), round(float(target_lon), 2))
                if cache_key in WeatherProvider._cache:
                    cached_epoch, cached_res = WeatherProvider._cache[cache_key]
                    if (time.time() - cached_epoch) < WeatherProvider._CACHE_TTL_SECONDS:
                        return cached_res

        def _calc_live_impact(code: int, precip: Optional[float], wind: Optional[float], base_imp: int) -> int:
            if base_imp == 0:
                return 0
            # Trace precipitation (<= 0.3mm) with non-gale wind (< 30km/h) for drizzle/slight rain has 0 delay
            if precip is not None and precip <= 0.3 and (wind is None or wind < 30.0) and code in (51, 53, 61, 80):
                return 0
            if baseline_eta_minutes is not None and baseline_eta_minutes > 0:
                if code in (51, 53, 55, 61, 80):
                    slowdown_pct = 0.08
                    min_floor = 0
                elif code in (45, 48, 63, 81):
                    slowdown_pct = 0.18
                    min_floor = 1
                elif code in (65, 82, 95, 96):
                    slowdown_pct = 0.30
                    min_floor = 2
                elif code in (71, 73, 75, 99):
                    slowdown_pct = 0.45
                    min_floor = 3
                else:
                    slowdown_pct = 0.10
                    min_floor = 0
                scaled = round(baseline_eta_minutes * slowdown_pct * weight)
                return max(min_floor, min(base_imp, scaled))
            return round(base_imp * weight)

        # 1. Attempt Open-Meteo Live API request if valid coordinates are present
        if target_lat is not None and target_lon is not None and weather_condition is None:
            if -90.0 <= target_lat <= 90.0 and -180.0 <= target_lon <= 180.0:
                try:
                    url = (
                        f"https://api.open-meteo.com/v1/forecast?"
                        f"latitude={target_lat}&longitude={target_lon}"
                        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m"
                        f"&hourly=precipitation_probability"
                        f"&timezone=UTC"
                    )
                    client_timeout = httpx.Timeout(6.0, connect=3.5)
                    async with httpx.AsyncClient(timeout=client_timeout) as client:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            data = resp.json()
                            curr = data.get("current") or data.get("current_weather") or {}
                            code = curr.get("weather_code") if "weather_code" in curr else curr.get("weathercode", 0)
                            temp = curr.get("temperature_2m") if "temperature_2m" in curr else curr.get("temperature", 20.0)

                            # Parse real apparent temperature (feels like)
                            app_temp_val = curr.get("apparent_temperature")
                            app_temp: Optional[float] = float(app_temp_val) if app_temp_val is not None else None

                            # Parse real relative humidity percentage
                            hum_val = curr.get("relative_humidity_2m")
                            humidity_pct: Optional[float] = float(hum_val) if hum_val is not None else None

                            # Parse forecast precipitation probability for current hour
                            hourly = data.get("hourly") or {}
                            precip_probs = hourly.get("precipitation_probability") or []
                            precip_prob_val: Optional[float] = (
                                float(precip_probs[0])
                                if (isinstance(precip_probs, list) and len(precip_probs) > 0 and precip_probs[0] is not None)
                                else None
                            )

                            # Parse real precipitation (None if not provided by feed)
                            precip_val = curr.get("precipitation") if "precipitation" in curr else curr.get("rain")
                            precip_float: Optional[float] = float(precip_val) if precip_val is not None else None

                            # Parse real wind metrics (None if not provided by feed)
                            ws_val = curr.get("wind_speed_10m") if "wind_speed_10m" in curr else curr.get("windspeed")
                            wind_speed: Optional[float] = float(ws_val) if ws_val is not None else None

                            wd_val = curr.get("wind_direction_10m") if "wind_direction_10m" in curr else curr.get("winddirection")
                            wind_dir: Optional[float] = float(wd_val) if wd_val is not None else None

                            # Parse actual Open-Meteo observation timestamp (preserve timezone correctness)
                            obs_time_str = curr.get("time")
                            if obs_time_str:
                                try:
                                    obs_dt = datetime.fromisoformat(obs_time_str)
                                    if obs_dt.tzinfo is None:
                                        obs_dt = obs_dt.replace(tzinfo=timezone.utc)
                                    sampled_time = obs_dt
                                except Exception:
                                    sampled_time = now
                            else:
                                sampled_time = now

                            data_age_sec = int((now - sampled_time).total_seconds()) if sampled_time else None
                            is_stale = data_age_sec is not None and data_age_sec > 10800  # > 3 hours

                            cond_label, base_imp = _WMO_WEATHER_MAP.get(code, ("Live Weather", 0))
                            if is_stale:
                                impact = 0
                                freshness = "STALE"
                                classification = "NOT_APPLIED"
                                applied = False
                            else:
                                impact = _calc_live_impact(code, precip_float, wind_speed, base_imp)
                                freshness = "FRESH"
                                classification = "INDEPENDENT_CONTEXT" if impact > 0 else "NOT_APPLIED"
                                applied = impact > 0

                            details = [f"{cond_label}", f"{temp}°C"]
                            if precip_float is not None:
                                details.append(f"Precip: {precip_float:.1f}mm")
                            if wind_speed is not None:
                                if wind_dir is not None:
                                    details.append(f"Wind: {wind_speed:.1f}km/h {wind_dir:.0f}°")
                                else:
                                    details.append(f"Wind: {wind_speed:.1f}km/h")
                            details_str = ", ".join(details)

                            if is_stale:
                                desc = (
                                    f"Weather ({details_str}): Open-Meteo observation is stale ({int(data_age_sec / 60)}m old > 180m threshold); "
                                    "ETA impact not applied — REAL / STALE."
                                )
                                rel_reason = "Weather observation is stale; ETA impact not applied."
                            elif impact > 0:
                                desc = (
                                    f"Weather ({details_str}): Open-Meteo live observation — REAL source data. "
                                    f"Adverse weather adjustment: +{impact} min delay — DERIVED."
                                )
                                rel_reason = f"Adverse weather conditions ({details_str}) justify derived +{impact}m adjustment."
                            else:
                                desc = (
                                    f"Weather ({details_str}): Open-Meteo live observation — REAL source data. "
                                    "Clear/mild transit conditions: 0 min delay applied — DERIVED."
                                )
                                rel_reason = "Current conditions are not severe enough to produce a measurable ETA impact."

                            res = ContextProviderResult(
                                source_name="Weather Data (Open-Meteo API)",
                                status=DataSourceStatus.STALE if is_stale else DataSourceStatus.AVAILABLE,
                                impact_minutes=impact,
                                description=desc,
                                sampled_at=sampled_time,
                                category="WEATHER",
                                provenance="REAL",
                                freshness=freshness,
                                impact_classification=classification,
                                provider_timestamp=obs_time_str or sampled_time.isoformat(),
                                fetched_timestamp=now.isoformat(),
                                data_age_seconds=data_age_sec,
                                applied_to_eta=applied,
                                relevance_reason=rel_reason,
                                precipitation_mm=precip_float,
                                wind_speed_kmh=wind_speed,
                                wind_direction_deg=wind_dir,
                                temperature_c=float(temp) if temp is not None else None,
                                apparent_temperature_c=app_temp,
                                humidity_percent=humidity_pct,
                                precipitation_probability_percent=precip_prob_val,
                                condition=cond_label,
                            )
                            if cache_key is not None:
                                WeatherProvider._cache[cache_key] = (time.time(), res)
                            return res
                except Exception as net_err:
                    if cache_key is not None and cache_key in WeatherProvider._cache:
                        logger.info("weather_cache_fallback", cache_key=cache_key, error=str(net_err))
                        return WeatherProvider._cache[cache_key][1]
                    logger.warning("weather_live_fetch_failed", error=str(net_err), lat=target_lat, lon=target_lon)

        # 2. Fallback: Dispatcher-supplied query param or default condition
        condition = (weather_condition or _DEFAULT_WEATHER).strip()
        key = condition.upper()

        base_impact = _WEATHER_IMPACT.get(key, 0)
        condition_recognized = key in _WEATHER_IMPACT

        if baseline_eta_minutes is not None and baseline_eta_minutes > 0 and base_impact > 0:
            if key in ("LIGHT RAIN", "DRIZZLE", "RAIN"):
                impact = max(0, min(base_impact, round(baseline_eta_minutes * 0.08 * weight)))
            elif key in ("HEAVY RAIN", "STORM", "THUNDERSTORM"):
                impact = max(2, min(base_impact, round(baseline_eta_minutes * 0.30 * weight)))
            elif key in ("SNOW", "BLIZZARD", "ICE"):
                impact = max(3, min(base_impact, round(baseline_eta_minutes * 0.45 * weight)))
            else:
                impact = round(base_impact * weight)
        else:
            impact = round(base_impact * weight) if base_impact > 0 else 0

        applied = impact > 0
        classification = "INDEPENDENT_CONTEXT" if applied else "NOT_APPLIED"

        if impact == 0:
            description = f"Weather: {condition} — clear transit conditions, no travel delay."
            rel_reason = "Current conditions are not severe enough to produce a measurable ETA impact."
        else:
            description = f"Weather: {condition} — adverse conditions add +{impact} min transit delay."
            rel_reason = f"Adverse weather conditions ({condition}) add +{impact} min transit delay."

        if not condition_recognized:
            description = (
                f"Weather condition '{condition}' not in classification table — "
                "zero delay applied conservatively."
            )
            rel_reason = f"Unrecognized weather condition '{condition}' — zero delay applied."

        return ContextProviderResult(
            source_name="Weather Data",
            status=DataSourceStatus.AVAILABLE,
            impact_minutes=impact,
            description=description,
            sampled_at=now,
            category="WEATHER",
            provenance="DERIVED",
            freshness="FRESH" if weather_condition else "UNKNOWN",
            impact_classification=classification,
            fetched_timestamp=now.isoformat(),
            applied_to_eta=applied,
            relevance_reason=rel_reason,
            condition=condition,
        )


# ── Traffic Data Provider ───────────────────────────────────────────────────────

class TrafficDataProvider(BaseContextProvider):
    """
    Production Real-Time Traffic Data Provider (Module 11 Upgrade).

    Integrates with legitimate open/public routing & traffic APIs (OSRM Driving Engine)
    or commercial traffic APIs (TomTom, OpenRouteService) based on environment configuration.

    Evaluates:
      - origin_lat, origin_lon (Technician current GPS fix)
      - dest_lat, dest_lon (Job location GPS coordinates)
      - baseline_eta_minutes (optional baseline comparison)

    Status rules:
      AVAILABLE   — Valid coordinates provided, external traffic API returned route/flow telemetry.
      UNAVAILABLE — Coords missing, provider disabled, API key missing when required,
                    or external network call timed out/failed.
      INVALID     — Out-of-bounds WGS84 coordinates or malformed API response.
      STALE       — Traffic data sampled beyond staleness threshold.

    Never throws unhandled exceptions or invents fake data; degrades safely to UNAVAILABLE with 0 impact.
    """

    async def evaluate(
        self,
        origin_lat: Optional[float] = None,
        origin_lon: Optional[float] = None,
        dest_lat: Optional[float] = None,
        dest_lon: Optional[float] = None,
        baseline_eta_minutes: Optional[int] = None,
        **kwargs,
    ) -> ContextProviderResult:
        now = datetime.now(timezone.utc)
        provider_type = (settings.TRAFFIC_PROVIDER or "osrm").strip().lower()

        if provider_type in ("none", "disabled"):
            return ContextProviderResult(
                source_name="Traffic Data",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description="Real-time traffic feed not integrated — set TRAFFIC_PROVIDER=osrm or tomtom in environment to enable.",
                sampled_at=now,
                category="TRAFFIC",
                provenance="UNAVAILABLE",
            )

        # Require valid origin and destination coordinates
        if origin_lat is None or origin_lon is None or dest_lat is None or dest_lon is None:
            return ContextProviderResult(
                source_name="Traffic Data",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description="Origin or destination GPS coordinates missing for traffic analysis (traffic feed not integrated).",
                sampled_at=now,
                category="TRAFFIC",
                provenance="UNAVAILABLE",
            )

        # Validate WGS84 bounds
        if not (
            _LAT_MIN <= origin_lat <= _LAT_MAX
            and _LON_MIN <= origin_lon <= _LON_MAX
            and _LAT_MIN <= dest_lat <= _LAT_MAX
            and _LON_MIN <= dest_lon <= _LON_MAX
        ):
            return ContextProviderResult(
                source_name="Traffic Data",
                status=DataSourceStatus.INVALID,
                impact_minutes=0,
                description=(
                    f"Traffic evaluation rejected — coordinates ({origin_lat:.4f}, {origin_lon:.4f}) "
                    f"-> ({dest_lat:.4f}, {dest_lon:.4f}) outside valid WGS84 bounds."
                ),
                sampled_at=now,
                category="TRAFFIC",
                provenance="UNAVAILABLE",
            )

        # Resolve TomTom API key from settings (TRAFFIC_API_KEY or TOMTOM_API_KEY)
        api_key = settings.TRAFFIC_API_KEY or getattr(settings, "TOMTOM_API_KEY", None)

        # Execute provider adapter call based on configured TRAFFIC_PROVIDER
        # If explicitly set to 'tomtom', or if an API key is provided and provider was not explicitly configured otherwise
        if provider_type == "tomtom" or (bool(api_key) and provider_type not in ("none", "disabled", "openrouteservice", "osrm", "osrm_only")):
            tomtom_res = await self._fetch_tomtom_traffic(
                origin_lat, origin_lon, dest_lat, dest_lon, baseline_eta_minutes, now, api_key=api_key
            )
            # Check if authoritative TomTom live routing succeeded with all required telemetry
            if (
                tomtom_res.status == DataSourceStatus.AVAILABLE
                and tomtom_res.provenance == "REAL"
                and tomtom_res.free_flow_travel_time_seconds is not None
                and tomtom_res.live_travel_time_seconds is not None
                and tomtom_res.routed_distance_meters is not None
            ):
                return tomtom_res

            # Fallback to OSRM road routing engine (Tier 2 fallback)
            try:
                osrm_res = await self._fetch_osrm_traffic(
                    origin_lat, origin_lon, dest_lat, dest_lon, baseline_eta_minutes, now
                )
                if (
                    osrm_res.status == DataSourceStatus.AVAILABLE
                    and osrm_res.provenance == "DERIVED"
                ):
                    return osrm_res
            except Exception:
                pass

            # Both TomTom and OSRM failed -> return TomTom failure result (UNAVAILABLE)
            return tomtom_res
        elif provider_type == "openrouteservice":
            return await self._fetch_openrouteservice_traffic(
                origin_lat, origin_lon, dest_lat, dest_lon, baseline_eta_minutes, now
            )
        else:
            # Default: OSRM (Open Source Routing Machine) public driving engine
            return await self._fetch_osrm_traffic(
                origin_lat, origin_lon, dest_lat, dest_lon, baseline_eta_minutes, now
            )

    async def _fetch_osrm_traffic(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        baseline_eta_minutes: Optional[int],
        now: datetime,
    ) -> ContextProviderResult:
        """Query OSRM (Open Source Routing Machine) public driving route engine."""
        base_url = settings.TRAFFIC_API_URL or "http://router.project-osrm.org"
        url = f"{base_url}/route/v1/driving/{origin_lon},{origin_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
        timeout = settings.TRAFFIC_TIMEOUT_SECONDS
        client_timeout = httpx.Timeout(timeout, connect=min(2.0, timeout))

        try:
            async with httpx.AsyncClient(timeout=client_timeout) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return ContextProviderResult(
                        source_name="Route Baseline (OSRM)",
                        status=DataSourceStatus.UNAVAILABLE,
                        impact_minutes=0,
                        description=f"OSRM routing service returned HTTP {response.status_code}. Fallback to straight-line baseline.",
                        sampled_at=now,
                        category="TRAFFIC",
                        provenance="UNAVAILABLE",
                    )
                data = response.json()

            if data.get("code") != "Ok" or not data.get("routes"):
                return ContextProviderResult(
                    source_name="Route Baseline (OSRM)",
                    status=DataSourceStatus.INVALID,
                    impact_minutes=0,
                    description="OSRM routing engine returned malformed or unrouteable response.",
                    sampled_at=now,
                    category="TRAFFIC",
                    provenance="UNAVAILABLE",
                )

            primary_route = data["routes"][0]
            driving_duration_sec = primary_route.get("duration", 0.0)
            driving_distance_meters = primary_route.get("distance", 0.0)
            driving_duration_min = max(1, round(driving_duration_sec / 60.0))
            route_coords = primary_route.get("geometry", {}).get("coordinates") if isinstance(primary_route.get("geometry"), dict) else None

            osrm_dist_km = round(driving_distance_meters / 1000.0, 2)
            osrm_dist_mi = round(osrm_dist_km / 1.60934, 2)

            desc = (
                f"Route (OSRM road baseline: {driving_duration_min} min, {osrm_dist_km} km): "
                "OSRM road routing is derived and does not provide live traffic flow."
            )

            return ContextProviderResult(
                source_name="Route Baseline (OSRM)",
                status=DataSourceStatus.AVAILABLE,
                impact_minutes=0,
                description=desc,
                sampled_at=now,
                category="TRAFFIC",
                provenance="DERIVED",
                freshness="FRESH",
                impact_classification="INCLUDED_IN_LIVE_ROUTE",
                fetched_timestamp=now.isoformat(),
                data_age_seconds=0,
                route_geometry=route_coords,
                free_flow_travel_time_seconds=int(driving_duration_sec),
                live_travel_time_seconds=int(driving_duration_sec),
                traffic_delay_seconds=0,
                routed_distance_meters=float(driving_distance_meters),
                routed_distance_miles=osrm_dist_mi,
                routed_distance_km=osrm_dist_km,
            )

        except httpx.TimeoutException:
            return ContextProviderResult(
                source_name="Route Baseline (OSRM)",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description=f"OSRM routing engine request timed out after {timeout}s — baseline ETA preserved.",
                sampled_at=now,
                category="TRAFFIC",
                provenance="UNAVAILABLE",
            )
        except Exception as exc:
            return ContextProviderResult(
                source_name="Route Baseline (OSRM)",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description=f"OSRM routing engine unreachable ({type(exc).__name__}) — baseline ETA preserved.",
                sampled_at=now,
                category="TRAFFIC",
                provenance="UNAVAILABLE",
            )

    async def _fetch_tomtom_traffic(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        baseline_eta_minutes: Optional[int],
        now: datetime,
        api_key: Optional[str] = None,
    ) -> ContextProviderResult:
        """Query TomTom Routing & Traffic API (requires TRAFFIC_API_KEY or TOMTOM_API_KEY)."""
        key = api_key or settings.TRAFFIC_API_KEY or getattr(settings, "TOMTOM_API_KEY", None)
        if not key:
            return ContextProviderResult(
                source_name="Traffic Data (TomTom API)",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description="TomTom Traffic API selected but API key (TRAFFIC_API_KEY) is not set in environment — 0 min delay applied.",
                sampled_at=now,
                category="TRAFFIC",
                provenance="UNAVAILABLE",
            )

        base_url = (settings.TRAFFIC_API_URL or "https://api.tomtom.com").rstrip("/")
        url = (
            f"{base_url}/routing/1/calculateRoute/"
            f"{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
            f"?key={key}&traffic=true"
        )
        timeout = settings.TRAFFIC_TIMEOUT_SECONDS
        client_timeout = httpx.Timeout(timeout, connect=min(2.0, timeout))

        try:
            async with httpx.AsyncClient(timeout=client_timeout) as client:
                res = await client.get(url)
                if res.status_code in (401, 403):
                    return ContextProviderResult(
                        source_name="Traffic Data (TomTom API)",
                        status=DataSourceStatus.UNAVAILABLE,
                        impact_minutes=0,
                        description=f"TomTom Traffic API authentication error (HTTP {res.status_code}): Invalid or unauthorized API key. Baseline ETA preserved.",
                        sampled_at=now,
                        category="TRAFFIC",
                        provenance="UNAVAILABLE",
                    )
                elif res.status_code == 400:
                    err_detail = "Unrouteable transit corridor"
                    try:
                        err_data = res.json()
                        err_detail = (
                            err_data.get("detailedError", {}).get("message")
                            or err_data.get("error")
                            or res.text[:120]
                        )
                    except Exception:
                        err_detail = res.text[:120]
                    return ContextProviderResult(
                        source_name="Traffic Data (TomTom API)",
                        status=DataSourceStatus.UNAVAILABLE,
                        impact_minutes=0,
                        description=(
                            f"TomTom Routing API reported unrouteable corridor: {err_detail}. "
                            "No driving route found between origin and destination coordinates. Baseline ETA preserved."
                        ),
                        sampled_at=now,
                        category="TRAFFIC",
                        provenance="UNAVAILABLE",
                    )
                elif res.status_code != 200:
                    return ContextProviderResult(
                        source_name="Traffic Data (TomTom API)",
                        status=DataSourceStatus.UNAVAILABLE,
                        impact_minutes=0,
                        description=f"TomTom Traffic API error (HTTP {res.status_code}). Baseline ETA preserved.",
                        sampled_at=now,
                        category="TRAFFIC",
                        provenance="UNAVAILABLE",
                    )
                data = res.json()

            if "routes" not in data or not data["routes"]:
                return ContextProviderResult(
                    source_name="Traffic Data (TomTom API)",
                    status=DataSourceStatus.INVALID,
                    impact_minutes=0,
                    description="TomTom Traffic API returned malformed response.",
                    sampled_at=now,
                    category="TRAFFIC",
                    provenance="UNAVAILABLE",
                )

            summary = data["routes"][0].get("summary", {})
            travel_time_sec = summary.get("travelTimeInSeconds", 0)
            traffic_delay_sec = summary.get("trafficDelayInSeconds")
            no_traffic_sec = summary.get("noTrafficTravelTimeInSeconds")
            length_in_meters = summary.get("lengthInMeters")

            if traffic_delay_sec is not None:
                delay_minutes = max(0, round(float(traffic_delay_sec) / 60.0))
            elif no_traffic_sec is not None:
                delay_minutes = max(0, round((float(travel_time_sec) - float(no_traffic_sec)) / 60.0))
            else:
                delay_minutes = 0

            # Free-flow duration resolution
            if no_traffic_sec is not None:
                effective_free_flow_sec = int(no_traffic_sec)
            elif traffic_delay_sec is not None:
                effective_free_flow_sec = max(0, int(travel_time_sec) - int(traffic_delay_sec))
            else:
                effective_free_flow_sec = int(travel_time_sec)

            travel_min = round(float(travel_time_sec) / 60.0)
            no_traffic_min = max(0, round(float(effective_free_flow_sec) / 60.0))

            routed_dist_km = round(float(length_in_meters) / 1000.0, 2) if length_in_meters is not None else None
            routed_dist_mi = round(routed_dist_km / 1.60934, 2) if routed_dist_km is not None else None

            ratio = travel_time_sec / max(1.0, float(effective_free_flow_sec))
            if ratio <= 1.05:
                condition = "Free Flow"
            elif ratio <= 1.25:
                condition = "Light Traffic"
            elif ratio <= 1.50:
                condition = "Moderate Traffic"
            else:
                condition = "Heavy Traffic"

            if delay_minutes > 0:
                desc = (
                    f"Traffic ({condition}): +{delay_minutes} min delay "
                    f"(TomTom live: {travel_min}m vs free-flow: {no_traffic_min}m). Source: TomTom Traffic API (REAL)."
                )
            else:
                desc = (
                    f"Traffic ({condition}): Normal transit conditions — no traffic delay "
                    f"(TomTom live: {travel_min}m). Source: TomTom Traffic API (REAL)."
                )

            legs = data["routes"][0].get("legs", [])
            tt_route_geom = None
            if legs and isinstance(legs, list) and len(legs) > 0:
                pts = legs[0].get("points", [])
                if pts and isinstance(pts, list):
                    tt_route_geom = [[p.get("longitude"), p.get("latitude")] for p in pts if "longitude" in p and "latitude" in p]

            return ContextProviderResult(
                source_name="Traffic Data (TomTom API)",
                status=DataSourceStatus.AVAILABLE,
                impact_minutes=delay_minutes,
                description=desc,
                sampled_at=now,
                category="TRAFFIC",
                provenance="REAL",
                freshness="FRESH",
                impact_classification="INCLUDED_IN_LIVE_ROUTE",
                provider_timestamp=now.isoformat(),
                fetched_timestamp=now.isoformat(),
                data_age_seconds=0,
                route_geometry=tt_route_geom,
                free_flow_travel_time_seconds=effective_free_flow_sec,
                live_travel_time_seconds=int(travel_time_sec),
                traffic_delay_seconds=int(traffic_delay_sec) if traffic_delay_sec is not None else int(travel_time_sec - effective_free_flow_sec),
                routed_distance_meters=float(length_in_meters) if length_in_meters is not None else None,
                routed_distance_miles=routed_dist_mi,
                routed_distance_km=routed_dist_km,
            )
        except httpx.TimeoutException:
            return ContextProviderResult(
                source_name="Traffic Data (TomTom API)",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description=f"TomTom Traffic API timed out after {timeout}s — 0 min delay applied.",
                sampled_at=now,
                category="TRAFFIC",
                provenance="UNAVAILABLE",
            )
        except Exception as exc:
            return ContextProviderResult(
                source_name="Traffic Data (TomTom API)",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description=f"TomTom Traffic API connection error ({type(exc).__name__}) — 0 min delay applied.",
                sampled_at=now,
                category="TRAFFIC",
                provenance="UNAVAILABLE",
            )

    async def _fetch_openrouteservice_traffic(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        baseline_eta_minutes: Optional[int],
        now: datetime,
    ) -> ContextProviderResult:
        """Query OpenRouteService Driving API (requires TRAFFIC_API_KEY)."""
        api_key = settings.TRAFFIC_API_KEY
        if not api_key:
            return ContextProviderResult(
                source_name="Traffic Data",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description="OpenRouteService API selected but API key (TRAFFIC_API_KEY) is not set in environment.",
                sampled_at=now,
                category="TRAFFIC",
            )

        base_url = settings.TRAFFIC_API_URL or "https://api.openrouteservice.org"
        url = f"{base_url}/v2/directions/driving-car?api_key={api_key}&start={origin_lon},{origin_lat}&end={dest_lon},{dest_lat}"
        timeout = settings.TRAFFIC_TIMEOUT_SECONDS

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return ContextProviderResult(
                        source_name="Traffic Data",
                        status=DataSourceStatus.UNAVAILABLE,
                        impact_minutes=0,
                        description=f"OpenRouteService error (HTTP {res.status_code}). Baseline ETA preserved.",
                        sampled_at=now,
                        category="TRAFFIC",
                    )
                data = res.json()

            summary = data["features"][0]["properties"]["summary"]
            duration_sec = summary.get("duration", 0)
            duration_min = round(duration_sec / 60.0)

            base_min = baseline_eta_minutes or max(1, duration_min)
            delay_minutes = max(0, duration_min - base_min)

            desc = f"Traffic: {duration_min} min driving time. Source: OpenRouteService."
            return ContextProviderResult(
                source_name="Traffic Data",
                status=DataSourceStatus.AVAILABLE,
                impact_minutes=delay_minutes,
                description=desc,
                sampled_at=now,
                category="TRAFFIC",
            )
        except httpx.TimeoutException:
            return ContextProviderResult(
                source_name="Traffic Data",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description=f"OpenRouteService timed out after {timeout}s.",
                sampled_at=now,
                category="TRAFFIC",
            )
        except Exception as exc:
            return ContextProviderResult(
                source_name="Traffic Data",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description=f"OpenRouteService connection error ({type(exc).__name__}).",
                sampled_at=now,
                category="TRAFFIC",
            )


# ── Spatial Corridor & Polyline Geometry Helpers ──────────────────────────────

def _point_to_corridor_projection(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    point_lat: float,
    point_lon: float,
) -> tuple[float, float, float]:
    """
    Computes corridor geometry metrics:
      - lateral_dist_mi: perpendicular distance in miles to the infinite line passing through origin and dest
      - segment_dist_mi: shortest distance in miles to the clamped line segment [origin, dest]
      - progress_t: along-track progress (0.0 = origin, 1.0 = destination)
    """
    import math
    from app.services.eta_service import _haversine_miles

    d_orig = _haversine_miles(origin_lat, origin_lon, point_lat, point_lon)
    d_dest = _haversine_miles(dest_lat, dest_lon, point_lat, point_lon)
    d_route = _haversine_miles(origin_lat, origin_lon, dest_lat, dest_lon)

    if d_route < 0.01:
        return (d_dest, d_dest, 1.0)

    mean_lat_rad = math.radians((origin_lat + dest_lat) / 2.0)
    cos_lat = math.cos(mean_lat_rad)

    dx_route = (dest_lon - origin_lon) * cos_lat * 69.172
    dy_route = (dest_lat - origin_lat) * 69.172

    dx_point = (point_lon - origin_lon) * cos_lat * 69.172
    dy_point = (point_lat - origin_lat) * 69.172

    route_len_sq = dx_route * dx_route + dy_route * dy_route
    if route_len_sq <= 0:
        return (d_dest, d_dest, 1.0)

    t = (dx_point * dx_route + dy_point * dy_route) / route_len_sq
    proj_x = t * dx_route
    proj_y = t * dy_route
    lateral_dist = math.sqrt((dx_point - proj_x) ** 2 + (dy_point - proj_y) ** 2)

    if t <= 0.0:
        segment_dist = d_orig
    elif t >= 1.0:
        segment_dist = d_dest
    else:
        segment_dist = lateral_dist

    return (lateral_dist, segment_dist, t)


def _perpendicular_distance_miles(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    point_lat: float,
    point_lon: float,
) -> float:
    """Computes shortest distance in miles from point to the line segment [origin, dest]."""
    _lat_dist, seg_dist, _t = _point_to_corridor_projection(
        origin_lat, origin_lon, dest_lat, dest_lon, point_lat, point_lon
    )
    return seg_dist


def _min_distance_to_route_polyline(
    polyline_coords: Optional[list],
    point_lat: float,
    point_lon: float,
) -> float:
    """
    Computes shortest distance in miles from (point_lat, point_lon) to any segment of a polyline.
    Handles GeoJSON [[lon, lat], ...] coordinates.
    """
    from app.services.eta_service import _haversine_miles

    if not polyline_coords or not isinstance(polyline_coords, list):
        return float("inf")

    n = len(polyline_coords)
    if n == 0:
        return float("inf")
    if n == 1:
        c = polyline_coords[0]
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            return _haversine_miles(point_lat, point_lon, float(c[1]), float(c[0]))
        return float("inf")

    min_dist = float("inf")
    step = 1 if n < 150 else max(1, n // 100)
    for i in range(0, n - 1, step):
        p1 = polyline_coords[i]
        next_idx = min(i + step, n - 1)
        p2 = polyline_coords[next_idx]
        if (
            isinstance(p1, (list, tuple))
            and isinstance(p2, (list, tuple))
            and len(p1) >= 2
            and len(p2) >= 2
        ):
            p1_lon, p1_lat = float(p1[0]), float(p1[1])
            p2_lon, p2_lat = float(p2[0]), float(p2[1])
            seg_dist = _perpendicular_distance_miles(p1_lat, p1_lon, p2_lat, p2_lon, point_lat, point_lon)
            if seg_dist < min_dist:
                min_dist = seg_dist

    return min_dist


STRICT_ROAD_CORRIDOR_BUFFER_METERS = 50.0   # 50 meters - strict point-only road corridor fallback buffer
STRICT_ROAD_CORRIDOR_BUFFER_MILES = 0.03   # ~50 meters (~160 ft) - backward compatibility
STRICT_EVENT_CORRIDOR_BUFFER_METERS = 400.0  # 400 meters - strict event venue corridor buffer
STRICT_EVENT_CORRIDOR_BUFFER_MILES = 0.25  # ~400 meters (1/4 mile) - backward compatibility


def _ccw_2d(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
    """Returns True if points a, b, c are in counter-clockwise order."""
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect_2d(
    p1: tuple[float, float],
    p2: tuple[float, float],
    r1: tuple[float, float],
    r2: tuple[float, float],
) -> bool:
    """Checks whether 2D line segment (p1, p2) intersects segment (r1, r2). Coordinates are (lon, lat)."""
    return (
        _ccw_2d(p1, r1, r2) != _ccw_2d(p2, r1, r2)
        and _ccw_2d(p1, p2, r1) != _ccw_2d(p1, p2, r2)
    )


def _linestring_to_route_distance(
    route_coords: Optional[list],
    incident_coords: Optional[list],
) -> float:
    """
    Computes minimum perpendicular distance in miles between incident geometry
    (LineString or MultiLineString coordinates) and the selected route polyline.
    Handles GeoJSON [[lon, lat], ...] or [[[lon, lat], ...], ...].

    Features:
      1. Exact segment-to-segment intersection detection (returns 0.0 if intersecting).
      2. Dense vertex and midpoint interpolation along incident segments.
    """
    if not route_coords or not incident_coords:
        return float("inf")

    # Extract list of line segments: [[(lon, lat), (lon, lat), ...], ...]
    lines: list[list[tuple[float, float]]] = []

    def _extract_lines(c):
        if not isinstance(c, (list, tuple)) or len(c) == 0:
            return
        if isinstance(c[0], (int, float)) and len(c) >= 2:
            return  # single point, not a line
        if isinstance(c[0], (list, tuple)) and len(c[0]) >= 2 and isinstance(c[0][0], (int, float)):
            # List of points -> a LineString
            line = [(float(pt[0]), float(pt[1])) for pt in c if len(pt) >= 2]
            if len(line) >= 2:
                lines.append(line)
        else:
            for sub in c:
                _extract_lines(sub)

    _extract_lines(incident_coords)

    # Convert route coords into (lon, lat) tuples
    route_pts = [
        (float(pt[0]), float(pt[1]))
        for pt in route_coords
        if isinstance(pt, (list, tuple)) and len(pt) >= 2
    ]
    if len(route_pts) < 2:
        return float("inf")

    # 1. First pass: exact segment-segment intersection check
    for line in lines:
        for i in range(len(line) - 1):
            p1 = line[i]
            p2 = line[i + 1]
            for j in range(len(route_pts) - 1):
                r1 = route_pts[j]
                r2 = route_pts[j + 1]
                if _segments_intersect_2d(p1, p2, r1, r2):
                    return 0.0  # Directly intersects selected route!

    # 2. Second pass: compute minimum distance from vertices and intermediate points to route
    min_dist = float("inf")
    for line in lines:
        sample_pts = []
        for i in range(len(line) - 1):
            p1 = line[i]
            p2 = line[i + 1]
            sample_pts.append(p1)
            # Add midpoints
            sample_pts.append(((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0))
        if line:
            sample_pts.append(line[-1])

        for lon, lat in sample_pts:
            d = _min_distance_to_route_polyline(route_coords, lat, lon)
            if d < min_dist:
                min_dist = d
                if min_dist <= 0.01:
                    return min_dist

    return min_dist


def _extract_points_from_geom(coords: Any) -> list[tuple[float, float]]:
    """Extract list of (lon, lat) tuples from GeoJSON coordinate structure."""
    pts: list[tuple[float, float]] = []
    if not coords or not isinstance(coords, (list, tuple)):
        return pts
    if len(coords) >= 2 and isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
        pts.append((float(coords[0]), float(coords[1])))
    else:
        for item in coords:
            pts.extend(_extract_points_from_geom(item))
    return pts


def _format_detour_evidence(detour_seconds: Optional[int]) -> str:
    """Format exact detour seconds into truthful human-readable evidence display."""
    if detour_seconds is None:
        return "No detour data available."
    if detour_seconds <= 0:
        return "No additional detour measured."

    minutes = detour_seconds // 60
    rem_seconds = detour_seconds % 60

    if minutes == 0:
        return f"{rem_seconds} sec additional (<1 min)"
    elif rem_seconds == 0:
        return f"{minutes} min additional"
    else:
        return f"{minutes} min {rem_seconds} sec additional"


def _format_incident_delay_evidence(delay_seconds: Optional[int]) -> str:
    """Format TomTom reported incident delay into truthful human-readable evidence display."""
    if delay_seconds is None:
        return "No incident delay reported."
    if delay_seconds <= 0:
        return "0 sec incident delay"

    rounded_min = max(1, round(delay_seconds / 60.0))
    return f"+{delay_seconds} sec (+{rounded_min} min)"


@dataclass
class DetourCalculationResult:
    detour_minutes: int
    alt_travel_time_seconds: Optional[int]
    explanation: str
    alternate_route_valid: bool = False
    alternate_route_available: bool = False
    detour_seconds: Optional[int] = None
    alternate_distance_meters: Optional[float] = None
    detour_display: Optional[str] = None

    def __iter__(self):
        yield self.detour_minutes
        yield self.alt_travel_time_seconds
        yield self.explanation

    def __getitem__(self, index):
        return (self.detour_minutes, self.alt_travel_time_seconds, self.explanation)[index]


async def _calculate_closure_detour(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    closure_lat: float,
    closure_lon: float,
    original_route_time_seconds: Optional[int],
    api_key: str,
    timeout_seconds: float = 4.0,
    closure_coords: Optional[list] = None,
) -> DetourCalculationResult:
    """
    Calculates derived detour travel time for a route-relevant road closure by querying
    TomTom Routing calculateRoute POST with an avoidArea bounding box around the closure.
    Avoids the entire affected geometry (LineString/MultiLineString) with a controlled ~100m buffer.
    Verifies that the returned alternate route does not still intersect the closure.
    """
    lat_buf = 0.0009  # ~100m lat buffer
    lon_buf = 0.0011  # ~100m lon buffer

    pts = _extract_points_from_geom(closure_coords) if closure_coords else []
    if pts:
        min_lon = min(p[0] for p in pts)
        max_lon = max(p[0] for p in pts)
        min_lat = min(p[1] for p in pts)
        max_lat = max(p[1] for p in pts)
        sw_lat = max(-90.0, min_lat - lat_buf)
        sw_lon = max(-180.0, min_lon - lon_buf)
        ne_lat = min(90.0, max_lat + lat_buf)
        ne_lon = min(180.0, max_lon + lon_buf)
    else:
        sw_lat = max(-90.0, closure_lat - lat_buf)
        sw_lon = max(-180.0, closure_lon - lon_buf)
        ne_lat = min(90.0, closure_lat + lat_buf)
        ne_lon = min(180.0, closure_lon + lon_buf)

    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute/"
        f"{origin_lat:.6f},{origin_lon:.6f}:{dest_lat:.6f},{dest_lon:.6f}/json"
    )
    params = {
        "key": api_key,
        "traffic": "true",
        "travelMode": "car",
    }
    body = {
        "avoidAreas": {
            "rectangles": [
                {
                    "southWestCorner": {"latitude": sw_lat, "longitude": sw_lon},
                    "northEastCorner": {"latitude": ne_lat, "longitude": ne_lon},
                }
            ]
        }
    }
    headers = {"Content-Type": "application/json"}

    try:
        client_timeout = httpx.Timeout(timeout_seconds, connect=min(2.0, timeout_seconds))
        async with httpx.AsyncClient(timeout=client_timeout) as client:
            resp = await client.post(url, params=params, json=body, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                routes = data.get("routes", [])
                if routes and isinstance(routes, list):
                    alt_route = routes[0]
                    alt_summary = alt_route.get("summary", {})
                    alt_time = alt_summary.get("travelTimeInSeconds")
                    alt_dist_m = alt_summary.get("lengthInMeters")
                    if alt_time is not None:
                        # Extract alternate route polyline points to verify avoidance (Section 6)
                        legs = alt_route.get("legs", [])
                        alt_pts = []
                        if legs and isinstance(legs, list) and len(legs) > 0:
                            raw_pts = legs[0].get("points", [])
                            if raw_pts and isinstance(raw_pts, list):
                                alt_pts = [[p.get("longitude", 0.0), p.get("latitude", 0.0)] for p in raw_pts if isinstance(p, dict)]

                        # Section 6: Check if alternate route still intersects closure geometry
                        still_intersects = False
                        if alt_pts and len(alt_pts) > 1:
                            if closure_coords and pts and len(pts) > 1:
                                dist_to_closure = _linestring_to_route_distance(alt_pts, closure_coords)
                                if dist_to_closure == float("inf"):
                                    dist_to_closure = min(_min_distance_to_route_polyline(alt_pts, p[1], p[0]) for p in pts)
                                still_intersects = (dist_to_closure <= 0.031)  # <= 50m
                            elif pts:
                                dist_to_closure = min(_min_distance_to_route_polyline(alt_pts, p[1], p[0]) for p in pts)
                                still_intersects = (dist_to_closure <= 0.031)  # <= 50m
                            else:
                                dist_to_closure = _min_distance_to_route_polyline(alt_pts, closure_lat, closure_lon)
                                still_intersects = (dist_to_closure <= 0.031)  # <= 50m

                        if still_intersects:
                            # Reject alternate route as invalid (Section 6)
                            return DetourCalculationResult(
                                detour_minutes=0,
                                alt_travel_time_seconds=None,
                                explanation="Alternate route still intersects the closed road segment — rejected as invalid; no verified avoidance route available (0 min delay applied).",
                                alternate_route_valid=False,
                                alternate_route_available=False,
                                detour_seconds=None,
                                alternate_distance_meters=alt_dist_m,
                            )

                        if original_route_time_seconds is not None and original_route_time_seconds > 0:
                            detour_sec = max(0, alt_time - original_route_time_seconds)
                            detour_min = max(0, round(detour_sec / 60.0))
                            det_disp = _format_detour_evidence(detour_sec)
                            alt_min = round(alt_time / 60.0)
                            orig_min = round(original_route_time_seconds / 60.0)
                            if detour_min > 0:
                                expl = (
                                    f"Alternate route: {alt_min} min vs original {orig_min} min (+{detour_min} min). "
                                    f"Detour derived from alternate route: {alt_min}m vs original {orig_min}m (+{detour_min} min delay). "
                                    f"Route-relevant closure — alternate route adds {detour_min} min."
                                )
                            elif detour_sec > 0:
                                expl = (
                                    f"Alternate route: {alt_min} min vs original {orig_min} min (+{detour_sec}s, <1 min). "
                                    f"Detour derived from alternate route: {alt_min}m vs original {orig_min}m (+{detour_sec}s detour delay, <1 min). "
                                    f"Route-relevant closure — alternate route adds {det_disp} (rounds to +0 min for ETA)."
                                )
                            else:
                                expl = (
                                    f"Alternate route: {alt_min} min vs original {orig_min} min (+0 min). "
                                    f"Route-relevant restriction detected — no additional detour time measured."
                                )
                        else:
                            detour_sec = 0
                            detour_min = 0
                            det_disp = "No additional detour measured."
                            expl = "Route-relevant restriction detected — no additional detour time measured."

                        return DetourCalculationResult(
                            detour_minutes=detour_min,
                            alt_travel_time_seconds=alt_time,
                            explanation=expl,
                            alternate_route_valid=True,
                            alternate_route_available=True,
                            detour_seconds=detour_sec,
                            alternate_distance_meters=alt_dist_m,
                            detour_display=det_disp,
                        )
                return DetourCalculationResult(
                    detour_minutes=0,
                    alt_travel_time_seconds=None,
                    explanation="Alternate route calculation unavailable (no routes returned) — no verified alternate-route detour could be calculated (0 min delay applied).",
                    alternate_route_valid=False,
                    alternate_route_available=False,
                    detour_seconds=None,
                )
            else:
                return DetourCalculationResult(
                    detour_minutes=0,
                    alt_travel_time_seconds=None,
                    explanation=f"Alternate route calculation unavailable (HTTP {resp.status_code}) — no verified alternate-route detour could be calculated (0 min delay applied).",
                    alternate_route_valid=False,
                    alternate_route_available=False,
                    detour_seconds=None,
                )
    except Exception as exc:
        return DetourCalculationResult(
            detour_minutes=0,
            alt_travel_time_seconds=None,
            explanation=f"Alternate route calculation unavailable ({type(exc).__name__}) — no verified alternate-route detour could be calculated (0 min delay applied).",
            alternate_route_valid=False,
            alternate_route_available=False,
            detour_seconds=None,
        )



# ── Events Data Provider ────────────────────────────────────────────────────────

class EventsDataProvider(BaseContextProvider):
    """
    Events & Public Gatherings Data Provider (PredictHQ integration).

    Evaluates live events, concerts, sports games, festivals, and public gatherings
    near the job destination coordinates using PredictHQ Events API.

    Validates:
      - Start and end timestamps (filters expired events: end_time < now)
      - Geographic relevance (filters events > 5 miles / 8 km from job destination)
      - Duplicate event IDs (deduplicates entries)

    Status & Provenance rules:
      AVAILABLE (provenance=REAL)          — PredictHQ response received with status 200. Active events evaluated.
      UNAVAILABLE (provenance=UNAVAILABLE) — Missing API key, network timeout, HTTP error, or unreachable.
      INVALID (provenance=UNAVAILABLE)     — Malformed response payload or invalid destination coordinates.

    When status is UNAVAILABLE or INVALID, impact_minutes is strictly 0 (safety enforcement).
    """

    CONGESTION_CATEGORIES = {
        "sports",
        "festivals",
        "concerts",
        "conferences",
        "expos",
        "community",
        "performing-arts",
    }

    async def evaluate(
        self,
        dest_lat: Optional[float] = None,
        dest_lon: Optional[float] = None,
        events_feed: Optional[list[dict]] = None,
        origin_lat: Optional[float] = None,
        origin_lon: Optional[float] = None,
        distance_miles: Optional[float] = None,
        baseline_eta_minutes: Optional[int] = None,
        route_geometry: Optional[list] = None,
        traffic_delay_seconds: Optional[int] = None,
        **kwargs,
    ) -> ContextProviderResult:
        now = datetime.now(timezone.utc)
        api_key = settings.EVENTS_API_KEY
        api_url = settings.EVENTS_API_URL or "https://api.predicthq.com/v1/events/"
        timeout_seconds = getattr(settings, "EVENTS_TIMEOUT_SECONDS", 4.0)

        # 1. Check coordinates if evaluating live feed
        if events_feed is None and (dest_lat is None or dest_lon is None):
            return ContextProviderResult(
                source_name="Events",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description="Destination coordinates missing or event feed not integrated — 0 min delay applied.",
                sampled_at=now,
                category="EVENTS",
                provenance="UNAVAILABLE",
                relevance_status="NOT_RELEVANT",
                relevance_reason="Destination coordinates missing or event feed not integrated",
                applied_to_eta=False,
            )

        if dest_lat is not None and dest_lon is not None:
            if not (-90.0 <= dest_lat <= 90.0 and -180.0 <= dest_lon <= 180.0):
                return ContextProviderResult(
                    source_name="Events",
                    status=DataSourceStatus.INVALID,
                    impact_minutes=0,
                    description=f"Invalid destination coordinates ({dest_lat}, {dest_lon}) — 0 min delay applied.",
                    sampled_at=now,
                    category="EVENTS",
                    provenance="UNAVAILABLE",
                    relevance_status="NOT_RELEVANT",
                    relevance_reason=f"Coordinates out of bounds: ({dest_lat}, {dest_lon})",
                    applied_to_eta=False,
                )

        # 2. Ingest events: either via test injection (events_feed) or live PredictHQ API call
        if events_feed is not None:
            raw_events = events_feed
        else:
            if not api_key:
                return ContextProviderResult(
                    source_name="Events",
                    status=DataSourceStatus.UNAVAILABLE,
                    impact_minutes=0,
                    description="Event & public gathering feed not configured: PredictHQ API key (EVENTS_API_KEY) not set in environment — 0 min delay applied.",
                    sampled_at=now,
                    category="EVENTS",
                    provenance="UNAVAILABLE",
                    relevance_status="NOT_RELEVANT",
                    relevance_reason="PredictHQ API key not configured",
                    applied_to_eta=False,
                )

            today_str = now.strftime("%Y-%m-%d")
            tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            params = {
                "limit": 10,
                "active.gte": today_str,
                "active.lte": tomorrow_str,
            }
            if dest_lat is not None and dest_lon is not None:
                params["within"] = f"5mi@{dest_lat},{dest_lon}"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            }

            try:
                client_timeout = httpx.Timeout(timeout_seconds, connect=min(2.0, timeout_seconds))
                async with httpx.AsyncClient(timeout=client_timeout) as client:
                    resp = await client.get(api_url, headers=headers, params=params)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if isinstance(data, dict):
                                raw_events = data.get("results")
                                if raw_events is None and "events" in data:
                                    raw_events = data.get("events")
                                if raw_events is None:
                                    raw_events = []
                            elif isinstance(data, list):
                                raw_events = data
                            else:
                                raw_events = []
                        except Exception:
                            return ContextProviderResult(
                                source_name="Events",
                                status=DataSourceStatus.INVALID,
                                impact_minutes=0,
                                description="Malformed JSON response received from PredictHQ — 0 min delay applied.",
                                sampled_at=now,
                                category="EVENTS",
                                provenance="UNAVAILABLE",
                                relevance_status="NOT_RELEVANT",
                                relevance_reason="Malformed JSON response received from PredictHQ",
                                applied_to_eta=False,
                            )
                    elif resp.status_code in (401, 403):
                        return ContextProviderResult(
                            source_name="Events",
                            status=DataSourceStatus.UNAVAILABLE,
                            impact_minutes=0,
                            description=f"PredictHQ authentication failed (HTTP {resp.status_code}) — 0 min delay applied.",
                            sampled_at=now,
                            category="EVENTS",
                            provenance="UNAVAILABLE",
                            relevance_status="NOT_RELEVANT",
                            relevance_reason=f"Authentication failed: HTTP {resp.status_code}",
                            applied_to_eta=False,
                        )
                    elif resp.status_code == 429:
                        return ContextProviderResult(
                            source_name="Events",
                            status=DataSourceStatus.UNAVAILABLE,
                            impact_minutes=0,
                            description="PredictHQ rate limit reached (HTTP 429) — 0 min delay applied.",
                            sampled_at=now,
                            category="EVENTS",
                            provenance="UNAVAILABLE",
                            relevance_status="NOT_RELEVANT",
                            relevance_reason="Rate limit reached: HTTP 429",
                            applied_to_eta=False,
                        )
                    else:
                        return ContextProviderResult(
                            source_name="Events",
                            status=DataSourceStatus.UNAVAILABLE,
                            impact_minutes=0,
                            description=f"PredictHQ returned HTTP {resp.status_code} — 0 min delay applied.",
                            sampled_at=now,
                            category="EVENTS",
                            provenance="UNAVAILABLE",
                            relevance_status="NOT_RELEVANT",
                            relevance_reason=f"API returned HTTP {resp.status_code}",
                            applied_to_eta=False,
                        )
            except httpx.TimeoutException:
                return ContextProviderResult(
                    source_name="Events",
                    status=DataSourceStatus.UNAVAILABLE,
                    impact_minutes=0,
                    description=f"PredictHQ request timed out after {timeout_seconds}s — 0 min delay applied.",
                    sampled_at=now,
                    category="EVENTS",
                    provenance="UNAVAILABLE",
                    relevance_status="NOT_RELEVANT",
                    relevance_reason=f"Request timed out after {timeout_seconds}s",
                    applied_to_eta=False,
                )
            except Exception as exc:
                return ContextProviderResult(
                    source_name="Events",
                    status=DataSourceStatus.UNAVAILABLE,
                    impact_minutes=0,
                    description=f"PredictHQ connection error: {type(exc).__name__} — 0 min delay applied.",
                    sampled_at=now,
                    category="EVENTS",
                    provenance="UNAVAILABLE",
                    relevance_status="NOT_RELEVANT",
                    relevance_reason=f"Connection error: {type(exc).__name__}",
                    applied_to_eta=False,
                )

        # 3. Parse and filter events
        valid_events = []
        seen_ids = set()

        for evt in raw_events:
            if not isinstance(evt, dict):
                continue
            evt_id = evt.get("id") or evt.get("name") or evt.get("title")
            if not evt_id or evt_id in seen_ids:
                continue

            title = evt.get("title") or evt.get("name") or "Public Event"
            category = (evt.get("category") or "event").lower()

            rank = evt.get("rank")
            try:
                rank = int(rank) if rank is not None else None
            except (ValueError, TypeError):
                rank = None

            attendance = evt.get("phq_attendance")
            try:
                attendance = int(attendance) if attendance is not None else None
            except (ValueError, TypeError):
                attendance = None

            # Validate expiration timestamp
            end_time_str = evt.get("end") or evt.get("end_time") or evt.get("start")
            if end_time_str:
                try:
                    clean_str = end_time_str.replace("Z", "+00:00")
                    end_dt = datetime.fromisoformat(clean_str)
                    if end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=timezone.utc)
                    if end_dt < now:
                        continue  # Expired event
                except ValueError:
                    pass

            # Validate geographic coordinates
            e_lat, e_lon = None, None
            loc = evt.get("location")
            if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                try:
                    e_lon, e_lat = float(loc[0]), float(loc[1])
                except (ValueError, TypeError):
                    pass
            elif isinstance(loc, dict):
                e_lat = loc.get("lat") or loc.get("latitude")
                e_lon = loc.get("lon") or loc.get("longitude") or loc.get("lng")

            if e_lat is None or e_lon is None:
                e_lat = evt.get("latitude") or evt.get("lat")
                e_lon = evt.get("longitude") or evt.get("lon") or evt.get("lng")

            # Extract location summary from geo address if available
            location_summary = None
            geo = evt.get("geo")
            if isinstance(geo, dict):
                address = geo.get("address")
                if isinstance(address, dict):
                    location_summary = address.get("formatted_address") or address.get("locality")
            if not location_summary:
                loc_name = evt.get("location_name") or evt.get("venue_name")
                if loc_name:
                    location_summary = str(loc_name)

            relevance = evt.get("relevance")
            try:
                relevance = float(relevance) if relevance is not None else None
            except (ValueError, TypeError):
                relevance = None

            dist_mi = None
            if dest_lat is not None and dest_lon is not None and e_lat is not None and e_lon is not None:
                from app.services.eta_service import _haversine_miles
                dist_mi = round(_haversine_miles(dest_lat, dest_lon, float(e_lat), float(e_lon)), 2)
                if dist_mi > 5.0:
                    continue  # Irrelevant location (> 5 miles from query zone)

            # Strict route-corridor evaluation: route polyline is primary spatial reference
            # Hierarchy: ROUTE GEOMETRY > 400m CORRIDOR BUFFER > NEVER BROAD RADIUS
            dist_to_route = None
            if e_lat is not None and e_lon is not None:
                if route_geometry and len(route_geometry) > 1:
                    dist_to_route = round(_min_distance_to_route_polyline(route_geometry, float(e_lat), float(e_lon)), 3)
                elif origin_lat is not None and origin_lon is not None and dest_lat is not None and dest_lon is not None:
                    lat_d, seg_d, t_prog = _point_to_corridor_projection(
                        origin_lat, origin_lon, dest_lat, dest_lon, float(e_lat), float(e_lon)
                    )
                    dist_to_route = round(seg_d, 3)
                else:
                    dist_to_route = dist_mi if dist_mi is not None else 999.0
            else:
                dist_to_route = 999.0

            dist_to_route_m = _miles_to_meters(dist_to_route) if dist_to_route is not None else 99999.0
            corridor_buffer_m = STRICT_EVENT_CORRIDOR_BUFFER_METERS
            dist_display = _format_metric_distance(dist_to_route_m)

            # Route relevance determination: strictly within route corridor buffer (400 m / 0.25 mi)
            is_relevant = dist_to_route_m <= corridor_buffer_m
            if is_relevant:
                rel_status = "RELEVANT"
                rel_reason = f"Event venue is {dist_display} from selected route (within 0.25 mi corridor buffer / {round(corridor_buffer_m)} m)"
            else:
                rel_status = "NOT_RELEVANT"
                rel_reason = f"Event venue is {dist_display} from selected route (outside 0.25 mi corridor buffer / {round(corridor_buffer_m)} m)"

            # Freshness validation for this event
            evt_start = evt.get("start")
            evt_end = evt.get("end") or evt.get("end_time")
            is_evt_stale = bool(evt.get("is_stale") or evt.get("freshness") == "STALE")
            evt_freshness = "STALE" if is_evt_stale else ("FRESH" if (evt_start or evt_end) else "UNKNOWN")

            # Causal Classification & ETA Impact calculation: evidence-based only, zero double-counting
            if is_evt_stale:
                event_delay = 0
                applied = False
                classification = "NOT_APPLIED"
                rel_reason += " | Event data is stale; ETA impact not applied."
            elif not is_relevant:
                event_delay = 0
                applied = False
                classification = "NOT_APPLIED"
            elif traffic_delay_seconds is not None and traffic_delay_seconds > 0:
                # Live traffic already captures corridor slowdown — avoid double-counting
                event_delay = 0
                applied = False
                classification = "INCLUDED_IN_LIVE_ROUTE"
                rel_reason += " | Event-related slowdown is already represented in live route travel time."
            elif evt.get("measured_delay_minutes") is not None:
                event_delay = max(0, int(evt["measured_delay_minutes"]))
                applied = event_delay > 0
                classification = "INDEPENDENT_CONTEXT" if applied else "NOT_APPLIED"
                if applied:
                    rel_reason += f" | Measured traffic delay (+{event_delay}m) (verified independent route delay)"
                else:
                    rel_reason += " | No measurable additional route slowdown detected (measurable ETA impact unavailable)."
            elif evt.get("legacy_impact") is not None:
                event_delay = max(0, int(evt["legacy_impact"]))
                applied = event_delay > 0
                classification = "INDEPENDENT_CONTEXT" if applied else "NOT_APPLIED"
                if applied:
                    rel_reason += f" | Measured traffic delay (+{event_delay}m) (verified route delay)"
                else:
                    rel_reason += " | No measurable additional route slowdown detected (measurable ETA impact unavailable)."
            else:
                # Event on route corridor, but normal traffic or no measurable slowdown established
                event_delay = 0
                applied = False
                classification = "NOT_APPLIED"
                rel_reason += " | No measurable additional route slowdown detected (measurable ETA impact unavailable)."

            seen_ids.add(evt_id)
            valid_events.append({
                "id": str(evt_id),
                "title": title,
                "category": category,
                "rank": rank,
                "attendance": attendance,
                "latitude": e_lat,
                "longitude": e_lon,
                "start": evt_start,
                "end": evt_end,
                "location_summary": location_summary,
                "dist_mi": dist_mi,
                "distance_to_route": dist_to_route,
                "distance_to_route_meters": dist_to_route_m,
                "distance_to_route_km": round(dist_to_route_m / 1000.0, 3),
                "distance_to_route_display": dist_display,
                "relevance": relevance,
                "is_route_relevant": is_relevant,
                "relevance_status": rel_status,
                "relevance_reason": rel_reason,
                "impact_minutes": event_delay,
                "impact_classification": classification,
                "freshness": evt_freshness,
                "applied_to_eta": applied,
            })

        if not valid_events:
            return ContextProviderResult(
                source_name="Events",
                status=DataSourceStatus.AVAILABLE,
                impact_minutes=0,
                description="No active public events affecting selected route corridor — 0 min delay applied. Source: PredictHQ (REAL).",
                sampled_at=now,
                category="EVENTS",
                provenance="REAL",
                freshness="FRESH",
                impact_classification="NOT_APPLIED",
                fetched_timestamp=now.isoformat(),
                event_count=0,
                is_route_relevant=False,
                relevance_status="NOT_RELEVANT",
                relevance_reason="No active public events detected along route corridor",
                applied_to_eta=False,
                corridor_buffer_meters=STRICT_EVENT_CORRIDOR_BUFFER_METERS,
                distance_to_route=None,
                evaluated_items=[],
            )

        # Sort so relevant events come first, then applied, then impact
        valid_events.sort(
            key=lambda x: (x.get("is_route_relevant", False), x.get("applied_to_eta", False), x.get("impact_minutes", 0)),
            reverse=True,
        )
        primary_event = valid_events[0]
        total_delay = min(15, sum(e["impact_minutes"] for e in valid_events if e.get("is_route_relevant", False)))
        primary_classification = primary_event.get("impact_classification", "NOT_APPLIED")

        if total_delay > 0:
            description = (
                f"Active public event ({primary_event['title']}) adds +{total_delay} min derived route delay. "
                f"Source: PredictHQ (REAL)."
            )
        else:
            relevant_count = sum(1 for e in valid_events if e.get("is_route_relevant", False))
            if primary_event.get("freshness") == "STALE":
                description = (
                    f"Active public event ({primary_event['title']}) data is stale; ETA impact not applied — 0 min delay. "
                    f"Source: PredictHQ (REAL / STALE)."
                )
            elif relevant_count > 0:
                if primary_classification == "INCLUDED_IN_LIVE_ROUTE":
                    description = (
                        f"Active public event ({primary_event['title']}) slowdown is already represented in live route travel time — 0 min additional delay. "
                        f"Source: PredictHQ (REAL)."
                    )
                else:
                    description = (
                        f"{len(valid_events)} nearby events detected ({relevant_count} route-relevant), but no measurable route slowdown — 0 min delay applied. "
                        f"Source: PredictHQ (REAL)."
                    )
            else:
                event_names = ", ".join(evt["title"] for evt in valid_events[:2])
                description = (
                    f"Active public events nearby ({event_names}) are outside route corridor (Route relevance: NOT RELEVANT) — 0 min delay applied. "
                    f"Source: PredictHQ (REAL)."
                )

        return ContextProviderResult(
            source_name="Events",
            status=DataSourceStatus.AVAILABLE,
            impact_minutes=total_delay,
            description=description,
            sampled_at=now,
            category="EVENTS",
            provenance="REAL",
            freshness=primary_event.get("freshness", "FRESH"),
            impact_classification=primary_classification,
            provider_timestamp=primary_event.get("start"),
            fetched_timestamp=now.isoformat(),
            event_count=len(valid_events),
            active_event_name=primary_event["title"],
            event_category=primary_event["category"],
            event_attendance=primary_event["attendance"],
            event_rank=primary_event["rank"],
            event_id=primary_event["id"],
            event_start=primary_event.get("start"),
            event_end=primary_event.get("end"),
            event_latitude=primary_event.get("latitude"),
            event_longitude=primary_event.get("longitude"),
            event_location_summary=primary_event.get("location_summary"),
            event_distance_miles=primary_event.get("dist_mi"),
            event_relevance=primary_event.get("relevance"),
            is_route_relevant=primary_event.get("is_route_relevant", False),
            relevance_status=primary_event.get("relevance_status", "NOT_RELEVANT"),
            relevance_reason=primary_event.get("relevance_reason"),
            applied_to_eta=total_delay > 0,
            corridor_buffer_meters=STRICT_EVENT_CORRIDOR_BUFFER_METERS,
            distance_to_route=primary_event.get("distance_to_route"),
            distance_to_route_meters=primary_event.get("distance_to_route_meters"),
            distance_to_route_km=primary_event.get("distance_to_route_km"),
            distance_to_route_display=primary_event.get("distance_to_route_display"),
            evaluated_items=valid_events,
        )


# ── Road Restriction Provider ───────────────────────────────────────────────────

_TOMTOM_RESTRICTION_CATEGORY_MAP = {
    0: "Unknown Incident",
    1: "Accident",
    2: "Fog",
    3: "Hazardous Conditions",
    4: "Rain",
    5: "Ice",
    6: "Traffic Jam",
    7: "Lane Closed",
    8: "Road Closed",
    9: "Road Works",
    10: "Wind Advisory",
    11: "Flooding",
    14: "Broken Down Vehicle",
}

_TOMTOM_RESTRICTION_MAGNITUDE_MAP = {
    0: "Minor / Informational",
    1: "Minor",
    2: "Moderate",
    3: "Major",
    4: "Blocking / Severe",
}


class RoadRestrictionProvider(BaseContextProvider):
    """
    TomTom Road Incidents & Restrictions Data Provider (Module 26).

    Evaluates active road closures, accidents, construction, and traffic restrictions
    along the technician's transit corridor towards the destination using the
    TomTom Traffic Incidents API (v5 incidentDetails).

    Safety & Provenance Guarantees:
      - REAL: Successful TomTom incident details HTTP 200 response parsed.
      - UNAVAILABLE: Missing coordinates, missing API key, network errors (401, 403, 429, 5xx),
        timeouts, or unreachable service -> strictly 0 min impact.
      - INVALID: Coordinates out of WGS84 bounds or malformed JSON payload -> strictly 0 min impact.
      - Zero Fake Data: If incident details cannot safely establish a delay, incident is preserved
        as REAL informational context with 0 min impact. Never fabricates delays or closures.
    """

    async def evaluate(
        self,
        origin_lat: Optional[float] = None,
        origin_lon: Optional[float] = None,
        dest_lat: Optional[float] = None,
        dest_lon: Optional[float] = None,
        restrictions_feed: Optional[list[dict]] = None,
        api_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        route_geometry: Optional[list] = None,
        distance_miles: Optional[float] = None,
        baseline_eta_minutes: Optional[int] = None,
        original_route_time_seconds: Optional[int] = None,
        traffic_delay_seconds: Optional[int] = None,
        **kwargs,
    ) -> ContextProviderResult:
        now = datetime.now(timezone.utc)

        # 1. Input coordinate validation (unless test feed provided)
        if restrictions_feed is None and (
            origin_lat is None or origin_lon is None or dest_lat is None or dest_lon is None
        ):
            return ContextProviderResult(
                source_name="Road Restrictions",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description="Road closure feed not integrated or coordinates missing — 0 min delay applied.",
                sampled_at=now,
                category="ROAD",
                provenance="UNAVAILABLE",
                relevance_status="NOT_RELEVANT",
                relevance_reason="Coordinates missing or feed not integrated",
                applied_to_eta=False,
            )

        if (
            origin_lat is not None
            and origin_lon is not None
            and dest_lat is not None
            and dest_lon is not None
        ):
            if not (
                _LAT_MIN <= origin_lat <= _LAT_MAX
                and _LON_MIN <= origin_lon <= _LON_MAX
                and _LAT_MIN <= dest_lat <= _LAT_MAX
                and _LON_MIN <= dest_lon <= _LON_MAX
            ):
                return ContextProviderResult(
                    source_name="Road Restrictions",
                    status=DataSourceStatus.INVALID,
                    impact_minutes=0,
                    description=(
                        f"Road restriction evaluation rejected — coordinates ({origin_lat:.4f}, {origin_lon:.4f}) "
                        f"-> ({dest_lat:.4f}, {dest_lon:.4f}) outside valid WGS84 bounds."
                    ),
                    sampled_at=now,
                    category="ROAD",
                    provenance="UNAVAILABLE",
                    relevance_status="NOT_RELEVANT",
                    relevance_reason="Coordinates outside valid WGS84 bounds",
                    applied_to_eta=False,
                )

        # 2. Ingest raw incident records: test feed or live TomTom Traffic Incidents API
        resolved_key = (
            api_key
            if api_key is not None
            else (settings.ROAD_RESTRICTION_API_KEY or settings.TOMTOM_API_KEY or settings.TRAFFIC_API_KEY)
        ) or None

        timeout = timeout_seconds or getattr(settings, "ROAD_RESTRICTION_TIMEOUT_SECONDS", 4.0)

        if restrictions_feed is not None:
            raw_closures = restrictions_feed
        else:
            if not resolved_key:
                return ContextProviderResult(
                    source_name="Road Restrictions",
                    status=DataSourceStatus.UNAVAILABLE,
                    impact_minutes=0,
                    description="Road closure feed not integrated or key missing (API key not configured) — 0 min delay applied.",
                    sampled_at=now,
                    category="ROAD",
                    provenance="UNAVAILABLE",
                    relevance_status="NOT_RELEVANT",
                    relevance_reason="TomTom Road Restrictions API key not configured",
                    applied_to_eta=False,
                )

            # Compute route corridor bounding box with ~3.5 mile margin
            import math
            margin = 0.05
            min_lat = max(-90.0, min(origin_lat, dest_lat) - margin)
            max_lat = min(90.0, max(origin_lat, dest_lat) + margin)
            min_lon = max(-180.0, min(origin_lon, dest_lon) - margin)
            max_lon = min(180.0, max(origin_lon, dest_lon) + margin)

            # TomTom incidentDetails restricts bbox area to <= 10,000 km2.
            lat_span_km = abs(max_lat - min_lat) * 111.0
            mid_lat_rad = math.radians((min_lat + max_lat) / 2.0)
            lon_span_km = abs(max_lon - min_lon) * 111.0 * abs(math.cos(mid_lat_rad))
            bbox_area_km2 = lat_span_km * lon_span_km

            # If corridor bbox exceeds TomTom's 10,000 km2 limit (e.g. distant points),
            # clamp the query bbox to destination service zone (~600 km2)
            if bbox_area_km2 > 9500.0:
                dest_margin = 0.08
                min_lat = max(-90.0, dest_lat - dest_margin)
                max_lat = min(90.0, dest_lat + dest_margin)
                min_lon = max(-180.0, dest_lon - dest_margin)
                max_lon = min(180.0, dest_lon + dest_margin)

            bbox = f"{min_lon:.5f},{min_lat:.5f},{max_lon:.5f},{max_lat:.5f}"

            api_url = settings.ROAD_RESTRICTION_API_URL or "https://api.tomtom.com/traffic/services/5/incidentDetails"
            fields = "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,events{description,code},startTime,endTime,from,to,length,delay}}}"
            params = {
                "key": resolved_key,
                "bbox": bbox,
                "language": "en-GB",
                "fields": fields,
            }

            try:
                client_timeout = httpx.Timeout(timeout, connect=min(2.0, timeout))
                async with httpx.AsyncClient(timeout=client_timeout) as client:
                    resp = await client.get(api_url, params=params)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if isinstance(data, dict):
                                raw_closures = data.get("incidents", [])
                                if raw_closures is None:
                                    raw_closures = []
                            elif isinstance(data, list):
                                raw_closures = data
                            else:
                                return ContextProviderResult(
                                    source_name="Road Restrictions",
                                    status=DataSourceStatus.INVALID,
                                    impact_minutes=0,
                                    description="Malformed response received from TomTom Traffic Incidents API — 0 min delay applied.",
                                    sampled_at=now,
                                    category="ROAD",
                                    provenance="UNAVAILABLE",
                                    relevance_status="NOT_RELEVANT",
                                    relevance_reason="Malformed response from TomTom API",
                                    applied_to_eta=False,
                                )
                        except Exception:
                            return ContextProviderResult(
                                source_name="Road Restrictions",
                                status=DataSourceStatus.INVALID,
                                impact_minutes=0,
                                description="Malformed JSON response received from TomTom Traffic Incidents API — 0 min delay applied.",
                                sampled_at=now,
                                category="ROAD",
                                provenance="UNAVAILABLE",
                                relevance_status="NOT_RELEVANT",
                                relevance_reason="Malformed JSON response from TomTom API",
                                applied_to_eta=False,
                            )
                    elif resp.status_code in (401, 403):
                        return ContextProviderResult(
                            source_name="Road Restrictions",
                            status=DataSourceStatus.UNAVAILABLE,
                            impact_minutes=0,
                            description=f"TomTom Road Restrictions authentication failed (HTTP {resp.status_code}): Invalid or unauthorized API key — 0 min delay applied.",
                            sampled_at=now,
                            category="ROAD",
                            provenance="UNAVAILABLE",
                            relevance_status="NOT_RELEVANT",
                            relevance_reason=f"Authentication failed: HTTP {resp.status_code}",
                            applied_to_eta=False,
                        )
                    elif resp.status_code == 429:
                        return ContextProviderResult(
                            source_name="Road Restrictions",
                            status=DataSourceStatus.UNAVAILABLE,
                            impact_minutes=0,
                            description="TomTom Road Restrictions rate limit reached (HTTP 429) — 0 min delay applied.",
                            sampled_at=now,
                            category="ROAD",
                            provenance="UNAVAILABLE",
                            relevance_status="NOT_RELEVANT",
                            relevance_reason="Rate limit reached: HTTP 429",
                            applied_to_eta=False,
                        )
                    elif resp.status_code >= 500:
                        return ContextProviderResult(
                            source_name="Road Restrictions",
                            status=DataSourceStatus.UNAVAILABLE,
                            impact_minutes=0,
                            description=f"TomTom Road Restrictions service unavailable (HTTP {resp.status_code}) — 0 min delay applied.",
                            sampled_at=now,
                            category="ROAD",
                            provenance="UNAVAILABLE",
                            relevance_status="NOT_RELEVANT",
                            relevance_reason=f"Service unavailable: HTTP {resp.status_code}",
                            applied_to_eta=False,
                        )
                    else:
                        err_text = ""
                        try:
                            err_data = resp.json()
                            err_text = err_data.get("message") or err_data.get("error") or ""
                        except Exception:
                            err_text = resp.text[:120]
                        err_msg = f": {err_text}" if err_text else ""
                        return ContextProviderResult(
                            source_name="Road Restrictions",
                            status=DataSourceStatus.UNAVAILABLE,
                            impact_minutes=0,
                            description=f"TomTom Road Restrictions API returned HTTP {resp.status_code}{err_msg} — 0 min delay applied.",
                            sampled_at=now,
                            category="ROAD",
                            provenance="UNAVAILABLE",
                            relevance_status="NOT_RELEVANT",
                            relevance_reason=f"API returned HTTP {resp.status_code}",
                            applied_to_eta=False,
                        )
            except httpx.TimeoutException:
                return ContextProviderResult(
                    source_name="Road Restrictions",
                    status=DataSourceStatus.UNAVAILABLE,
                    impact_minutes=0,
                    description=f"TomTom Road Restrictions request timed out after {timeout}s — 0 min delay applied.",
                    sampled_at=now,
                    category="ROAD",
                    provenance="UNAVAILABLE",
                    relevance_status="NOT_RELEVANT",
                    relevance_reason=f"Request timed out after {timeout}s",
                    applied_to_eta=False,
                )
            except Exception as exc:
                return ContextProviderResult(
                    source_name="Road Restrictions",
                    status=DataSourceStatus.UNAVAILABLE,
                    impact_minutes=0,
                    description=f"TomTom Road Restrictions connection error: {type(exc).__name__} — 0 min delay applied.",
                    sampled_at=now,
                    category="ROAD",
                    provenance="UNAVAILABLE",
                    relevance_status="NOT_RELEVANT",
                    relevance_reason=f"Connection error: {type(exc).__name__}",
                    applied_to_eta=False,
                )

        # 3. Parse and filter incidents
        valid_incidents = []
        seen_ids = set()
        seen_physical_closures = set()
        cached_closure_detour: Optional[DetourCalculationResult] = None

        for item in raw_closures:
            if not isinstance(item, dict):
                continue

            props = item.get("properties") if isinstance(item.get("properties"), dict) else item
            inc_id = props.get("id") or item.get("id") or props.get("road_name")
            if not inc_id or inc_id in seen_ids:
                continue

            # Expiration timestamp validation
            exp_str = props.get("endTime") or props.get("expires_at") or props.get("end")
            if exp_str:
                try:
                    clean_str = str(exp_str).replace("Z", "+00:00")
                    exp_dt = datetime.fromisoformat(clean_str)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                    if exp_dt < now and not (props.get("is_stale") or props.get("freshness") == "STALE" or item.get("freshness") == "STALE"):
                        continue  # Expired incident
                except (ValueError, TypeError):
                    pass

            # Extract coordinates and geometry
            c_lat, c_lon = None, None
            geom = item.get("geometry")
            has_geometry = False
            geom_coords = None

            if isinstance(geom, dict):
                geom_coords = geom.get("coordinates")
                g_type = geom.get("type")
                if g_type == "Point" and isinstance(geom_coords, (list, tuple)) and len(geom_coords) >= 2:
                    try:
                        c_lon, c_lat = float(geom_coords[0]), float(geom_coords[1])
                    except (ValueError, TypeError):
                        pass
                elif g_type in ("LineString", "MultiLineString") and isinstance(geom_coords, (list, tuple)) and len(geom_coords) > 0:
                    has_geometry = True
                    # Extract representative mid point for fallback / coordinates
                    if g_type == "LineString":
                        mid = geom_coords[len(geom_coords) // 2]
                        if isinstance(mid, (list, tuple)) and len(mid) >= 2:
                            try:
                                c_lon, c_lat = float(mid[0]), float(mid[1])
                            except (ValueError, TypeError):
                                pass
                    elif g_type == "MultiLineString" and len(geom_coords[0]) > 0:
                        mid = geom_coords[0][len(geom_coords[0]) // 2]
                        if isinstance(mid, (list, tuple)) and len(mid) >= 2:
                            try:
                                c_lon, c_lat = float(mid[0]), float(mid[1])
                            except (ValueError, TypeError):
                                pass

            if c_lat is None or c_lon is None:
                raw_lat = props.get("latitude") or props.get("lat")
                raw_lon = props.get("longitude") or props.get("lon") or props.get("lng")
                if raw_lat is not None and raw_lon is not None:
                    try:
                        c_lat, c_lon = float(raw_lat), float(raw_lon)
                    except (ValueError, TypeError):
                        pass

            # Geographic route relevance filtering
            # Selected TomTom route geometry from Step 1 is the authoritative spatial reference.
            dist_dest_mi = None
            dist_orig_mi = None
            dist_to_route = None

            if (
                origin_lat is not None
                and origin_lon is not None
                and dest_lat is not None
                and dest_lon is not None
                and c_lat is not None
                and c_lon is not None
            ):
                from app.services.eta_service import _haversine_miles
                dist_dest_mi = round(_haversine_miles(dest_lat, dest_lon, c_lat, c_lon), 2)
                dist_orig_mi = round(_haversine_miles(origin_lat, origin_lon, c_lat, c_lon), 2)

                # Discard completely distant incidents located beyond query area (> 5 miles from both terminals)
                # Only if route geometry polyline is not available
                if min(dist_dest_mi, dist_orig_mi) > 5.0 and not (route_geometry and len(route_geometry) > 1):
                    continue

                if has_geometry and route_geometry and len(route_geometry) > 1:
                    # Priority 1: Affected road geometry (LineString/MultiLineString) intersection / overlap
                    dist_to_route = round(_linestring_to_route_distance(route_geometry, geom_coords), 3)
                    dist_to_route_m = _miles_to_meters(dist_to_route)
                    corridor_buffer_m = STRICT_ROAD_CORRIDOR_BUFFER_METERS
                    corridor_buffer = STRICT_ROAD_CORRIDOR_BUFFER_MILES
                    is_route_relevant = dist_to_route == 0.0 or dist_to_route_m <= corridor_buffer_m
                elif route_geometry and len(route_geometry) > 1:
                    # Priority 2: Point incident evaluated against 50m fallback corridor
                    dist_to_route = round(_min_distance_to_route_polyline(route_geometry, c_lat, c_lon), 3)
                    dist_to_route_m = _miles_to_meters(dist_to_route)
                    corridor_buffer_m = STRICT_ROAD_CORRIDOR_BUFFER_METERS
                    corridor_buffer = STRICT_ROAD_CORRIDOR_BUFFER_MILES
                    is_route_relevant = dist_to_route_m <= corridor_buffer_m
                else:
                    # Fallback straight-line corridor projection when routing engine polyline is unavailable
                    lat_d, seg_d, t_prog = _point_to_corridor_projection(
                        origin_lat, origin_lon, dest_lat, dest_lon, c_lat, c_lon
                    )
                    dist_to_route = round(seg_d, 3)
                    dist_to_route_m = _miles_to_meters(dist_to_route)
                    corridor_buffer_m = 120.0  # ~120m corridor buffer for straight-line projection
                    corridor_buffer = 0.08
                    is_route_relevant = bool(lat_d <= corridor_buffer and -0.10 <= t_prog <= 1.10)
            else:
                dist_to_route = 999.0
                dist_to_route_m = 99999.0
                is_route_relevant = False
                corridor_buffer = STRICT_ROAD_CORRIDOR_BUFFER_MILES
                corridor_buffer_m = STRICT_ROAD_CORRIDOR_BUFFER_METERS

            dist_display = _format_metric_distance(dist_to_route_m)

            # Check for duplicate incident id or coordinates
            dup_key = str(inc_id)
            if dup_key in seen_ids:
                continue

            # Extract human-readable metadata
            road_from = props.get("from") or props.get("road_from")
            road_to = props.get("to") or props.get("road_to")
            if road_from and road_to:
                road_name = f"{road_from} to {road_to}"
            elif road_from:
                road_name = road_from
            elif road_to:
                road_name = road_to
            else:
                road_name = props.get("road_name") or "Transit Corridor"

            # Parse incident attributes
            icon_cat = props.get("iconCategory")
            cat_int = int(icon_cat) if icon_cat is not None else 0
            cat_name = _TOMTOM_RESTRICTION_CATEGORY_MAP.get(cat_int, props.get("category") or "Road Incident")

            mag_val = props.get("magnitudeOfDelay")
            mag_int = int(mag_val) if mag_val is not None else 0
            severity_name = _TOMTOM_RESTRICTION_MAGNITUDE_MAP.get(mag_int, props.get("severity") or "Minor")

            events = props.get("events") or []
            event_descs = [e.get("description") for e in events if isinstance(e, dict) and e.get("description")]
            desc_summary = ", ".join(event_descs) if event_descs else props.get("description") or cat_name

            delay_s = props.get("delay")

            explicit_closed = props.get("is_closed")
            if explicit_closed is None:
                explicit_closed = props.get("is_road_closed")

            if explicit_closed is not None:
                is_closed = bool(explicit_closed)
            else:
                is_closed = bool(
                    cat_int == 8
                    or "road closed" in desc_summary.lower()
                    or "road closure" in desc_summary.lower()
                    or "corridor closed" in desc_summary.lower()
                )

            # Freshness evaluation for incident
            inc_start = props.get("startTime") or props.get("start")
            inc_end = props.get("endTime") or props.get("end") or exp_str
            is_inc_stale = bool(props.get("is_stale") or props.get("freshness") == "STALE" or item.get("freshness") == "STALE")
            if not is_inc_stale and inc_end:
                try:
                    end_dt = datetime.fromisoformat(str(inc_end).replace("Z", "+00:00"))
                    if end_dt < now:
                        is_inc_stale = True
                except Exception:
                    pass
            inc_freshness = "STALE" if is_inc_stale else ("FRESH" if (inc_start or inc_end) else "UNKNOWN")

            # Relevance decision explanation
            if is_route_relevant:
                rel_status = "RELEVANT"
                if has_geometry:
                    if dist_to_route == 0.0:
                        rel_reason = "Affected road geometry intersects selected route"
                    else:
                        rel_reason = f"Affected road segment is within {dist_display} of selected route"
                else:
                    rel_reason = f"Incident location is on selected route corridor ({dist_display} <= {round(corridor_buffer_m)} m point-only route-corridor fallback)"
            else:
                rel_status = "NOT_RELEVANT"
                rel_reason = f"Road restriction detected {dist_display} from route — not affecting this route (outside selected route corridor)."

            # ETA Impact & Detour calculation with truthful evidence semantics
            inc_delay = 0
            detour_time_min = None
            applied = False
            classification = "NOT_APPLIED"
            causal_status = "NOT_RELEVANT"
            alt_route_avail = False
            alt_route_val = False
            alt_time_sec = None
            det_sec = None
            inc_delay_sec = None
            det_disp = None

            if is_inc_stale:
                inc_delay = 0
                applied = False
                classification = "NOT_APPLIED"
                causal_status = "STALE"
                rel_reason = f"Road restriction ({road_name}) data is stale; ETA impact not applied — 0 min delay applied."
            elif not is_route_relevant:
                inc_delay = 0
                applied = False
                classification = "NOT_APPLIED"
                causal_status = "NOT_RELEVANT"
                rel_reason = f"Road restriction detected {dist_display} from route — not affecting this route (outside selected route corridor)."
            elif is_closed:
                # Priority: verified closure on selected route
                alt_geom = item.get("alternate_route_geometry")
                alt_reintersects = False
                if alt_geom and len(alt_geom) > 1:
                    if has_geometry and geom_coords:
                        d_alt = _linestring_to_route_distance(alt_geom, geom_coords)
                        if d_alt == float("inf"):
                            d_alt = _min_distance_to_route_polyline(alt_geom, c_lat, c_lon)
                        alt_reintersects = (d_alt <= 0.031)  # <= 50m
                    else:
                        d_alt = _min_distance_to_route_polyline(alt_geom, c_lat, c_lon)
                        alt_reintersects = (d_alt <= 0.031)  # <= 50m

                if item.get("causal_status") == "INCLUDED_IN_LIVE_ROUTE" or item.get("is_avoided_by_live_route") is True:
                    inc_delay = 0
                    det_sec = 0
                    det_disp = "No additional detour measured."
                    applied = False
                    classification = "INCLUDED_IN_LIVE_ROUTE"
                    causal_status = "INCLUDED_IN_LIVE_ROUTE"
                    rel_reason += " | Selected live route already avoids restriction (no additional detour)."
                elif alt_reintersects:
                    # Section 6: Reject alternate route as invalid
                    inc_delay = 0
                    det_sec = None
                    det_disp = None
                    applied = False
                    classification = "NOT_APPLIED"
                    causal_status = "UNAVAILABLE"
                    alt_route_avail = False
                    alt_route_val = False
                    rel_reason += " | Alternate route still intersects the closed road segment — rejected as invalid; no verified avoidance route available (0 min delay applied)."
                elif item.get("alternate_route_time_seconds") is not None and original_route_time_seconds is not None:
                    alt_sec = int(item["alternate_route_time_seconds"])
                    orig_sec = int(original_route_time_seconds)
                    detour_sec = max(0, alt_sec - orig_sec)
                    inc_delay = max(0, round(detour_sec / 60.0))
                    det_sec = detour_sec
                    det_disp = _format_detour_evidence(detour_sec)
                    detour_time_min = round(alt_sec / 60.0)
                    orig_time_min = round(orig_sec / 60.0)
                    alt_time_sec = alt_sec
                    alt_route_avail = True
                    alt_route_val = True
                    applied = inc_delay > 0
                    if detour_sec > 0:
                        classification = "INCREMENTAL_DETOUR"
                        causal_status = "RELEVANT_INCREMENTAL_DETOUR"
                        if inc_delay > 0:
                            rel_reason += (
                                f" | Alternate route: {detour_time_min} min vs original {orig_time_min} min (+{inc_delay} min). "
                                f"Detour derived from alternate route: {detour_time_min}m vs original {orig_time_min}m (+{inc_delay} min delay)"
                            )
                        else:
                            rel_reason += (
                                f" | Alternate route: {detour_time_min} min vs original {orig_time_min} min (+{detour_sec}s, <1 min). "
                                f"Detour derived from alternate route: {detour_time_min}m vs original {orig_time_min}m (+{detour_sec}s detour delay, <1 min). "
                                f"Route-relevant closure — alternate route adds {det_disp} (rounds to +0 min for ETA)."
                            )
                    else:
                        classification = "INCLUDED_IN_LIVE_ROUTE"
                        causal_status = "RELEVANT_NO_ADDITIONAL_DETOUR"
                        rel_reason += f" | Alternate route: {detour_time_min} min vs original {orig_time_min} min (+0 min). Route-relevant restriction detected — no additional detour time measured."
                elif resolved_key and origin_lat and origin_lon and dest_lat and dest_lon and c_lat and c_lon and delay_s is None:
                    if cached_closure_detour is None:
                        det_res = await _calculate_closure_detour(
                            origin_lat=origin_lat,
                            origin_lon=origin_lon,
                            dest_lat=dest_lat,
                            dest_lon=dest_lon,
                            closure_lat=c_lat,
                            closure_lon=c_lon,
                            original_route_time_seconds=original_route_time_seconds,
                            api_key=resolved_key,
                            timeout_seconds=timeout,
                            closure_coords=geom_coords,
                        )
                        cached_closure_detour = det_res
                    else:
                        det_res = cached_closure_detour

                    inc_delay = det_res.detour_minutes
                    alt_time_sec = det_res.alt_travel_time_seconds
                    det_sec = det_res.detour_seconds
                    det_disp = det_res.detour_display or _format_detour_evidence(det_sec)
                    alt_route_avail = det_res.alternate_route_available
                    alt_route_val = det_res.alternate_route_valid
                    detour_time_min = round(alt_time_sec / 60.0) if alt_time_sec is not None else None

                    if not det_res.alternate_route_available or not det_res.alternate_route_valid:
                        applied = False
                        classification = "NOT_APPLIED"
                        causal_status = "UNAVAILABLE"
                        inc_delay = 0
                        det_sec = None
                        det_disp = None
                        rel_reason += f" | {det_res.explanation}"
                    elif inc_delay > 0:
                        applied = True
                        classification = "INCREMENTAL_DETOUR"
                        causal_status = "RELEVANT_INCREMENTAL_DETOUR"
                        rel_reason += f" | {det_res.explanation}"
                    elif det_sec is not None and det_sec > 0:
                        applied = False
                        classification = "INCREMENTAL_DETOUR"
                        causal_status = "RELEVANT_INCREMENTAL_DETOUR"
                        rel_reason += f" | {det_res.explanation}"
                    else:
                        applied = False
                        classification = "INCLUDED_IN_LIVE_ROUTE"
                        causal_status = "RELEVANT_NO_ADDITIONAL_DETOUR"
                        rel_reason += f" | {det_res.explanation}"
                elif is_closed and delay_s is not None and delay_s > 0:
                    # Direct closure delay reported by provider (fallback when alternate routing not invoked)
                    inc_delay = max(0, round(float(delay_s) / 60.0))
                    inc_delay_sec = int(delay_s)
                    det_sec = None
                    det_disp = _format_incident_delay_evidence(inc_delay_sec)
                    applied = inc_delay > 0
                    classification = "RELEVANT_INCIDENT_DELAY" if inc_delay > 0 else "NOT_APPLIED"
                    causal_status = "RELEVANT_INCIDENT_DELAY" if inc_delay > 0 else "RELEVANT_NO_ADDITIONAL_DETOUR"
                    rel_reason += f" | Reported closure delay: {det_disp}"
                elif item.get("impact_minutes") is not None and item.get("alternate_route_available"):
                    inc_delay = max(0, int(item["impact_minutes"]))
                    det_sec = inc_delay * 60
                    applied = inc_delay > 0
                    alt_route_avail = True
                    alt_route_val = True
                    det_disp = _format_detour_evidence(det_sec)
                    if applied:
                        classification = "INCREMENTAL_DETOUR"
                        causal_status = "RELEVANT_INCREMENTAL_DETOUR"
                        rel_reason += f" | Route-relevant closure — alternate route adds {inc_delay} min."
                    else:
                        classification = "INCLUDED_IN_LIVE_ROUTE"
                        causal_status = "RELEVANT_NO_ADDITIONAL_DETOUR"
                        rel_reason += " | Route-relevant restriction detected — no additional detour time measured."
                else:
                    # Closure verified on route, but alternate route calculation unavailable
                    # ZERO FAKE DATA POLICY: Do NOT invent arbitrary +15/+30 min
                    inc_delay = 0
                    det_sec = None
                    applied = False
                    classification = "NOT_APPLIED"
                    causal_status = "UNAVAILABLE"
                    alt_route_avail = False
                    alt_route_val = False
                    rel_reason += " | Alternate route calculation unavailable — no verified alternate-route detour could be calculated (0 min delay applied)."
            elif traffic_delay_seconds is not None and traffic_delay_seconds > 0:
                # Route slowdown already included in authoritative live route travel time
                inc_delay = 0
                det_sec = None
                inc_delay_sec = int(delay_s) if delay_s is not None else None
                applied = False
                classification = "INCLUDED_IN_LIVE_ROUTE"
                causal_status = "RELEVANT_NO_ADDITIONAL_DETOUR"
                rel_reason += " | Route slowdown already accounted for in authoritative live route traffic delay (no double-counting)"
            elif delay_s is not None and delay_s > 0:
                inc_delay = max(0, round(float(delay_s) / 60.0))
                det_sec = None
                inc_delay_sec = int(delay_s)
                applied = inc_delay > 0
                classification = "RELEVANT_INCIDENT_DELAY"
                causal_status = "RELEVANT_INCIDENT_DELAY"
                det_disp = None
                rel_reason += f" | TomTom reported incident delay: {_format_incident_delay_evidence(inc_delay_sec)}"
            elif item.get("impact_minutes") is not None:
                inc_delay = max(0, int(item["impact_minutes"]))
                inc_delay_sec = item.get("incident_delay_seconds") or (inc_delay * 60)
                det_sec = None
                applied = inc_delay > 0
                classification = "RELEVANT_INCIDENT_DELAY" if applied else "NOT_APPLIED"
                causal_status = "RELEVANT_INCIDENT_DELAY" if applied else "RELEVANT_NO_ADDITIONAL_DETOUR"
                det_disp = None
                rel_reason += f" | TomTom reported incident delay: {_format_incident_delay_evidence(inc_delay_sec)}" if applied else " | Minor restriction with no reported delay"
            else:
                inc_delay = 0
                det_sec = None
                inc_delay_sec = None
                applied = False
                classification = "NOT_APPLIED"
                causal_status = "RELEVANT_NO_ADDITIONAL_DETOUR"
                rel_reason += " | Minor/informational restriction on route with no reported delay — 0 min delay applied"


            # Deduplicate physical closures along the corridor (Step 6)
            norm_road = road_name.lower().strip() if road_name else ""
            closure_loc_key = (norm_road, round(c_lat or 0, 3), round(c_lon or 0, 3)) if (c_lat is not None and c_lon is not None) else None
            if is_closed and is_route_relevant and closure_loc_key and closure_loc_key in seen_physical_closures:
                continue

            seen_ids.add(str(inc_id))
            if is_closed and is_route_relevant and closure_loc_key:
                seen_physical_closures.add(closure_loc_key)

            valid_incidents.append({
                "id": str(inc_id),
                "road_name": road_name,
                "category_name": cat_name,
                "severity_name": severity_name,
                "desc_summary": desc_summary,
                "delay_min": inc_delay,
                "delay_sec": int(delay_s) if delay_s is not None else None,
                "is_closed": is_closed,
                "start": inc_start,
                "end": inc_end,
                "dist_mi": dist_dest_mi if dist_dest_mi is not None else dist_to_route,
                "distance_to_route": dist_to_route,
                "distance_to_route_meters": dist_to_route_m,
                "distance_to_route_km": round(dist_to_route_m / 1000.0, 3),
                "distance_to_route_display": dist_display,
                "latitude": c_lat,
                "longitude": c_lon,
                "magnitude": mag_int,
                "is_route_relevant": is_route_relevant,
                "relevance_status": rel_status,
                "relevance_reason": rel_reason,
                "impact_minutes": inc_delay,
                "impact_classification": classification,
                "freshness": inc_freshness,
                "applied_to_eta": applied,
                "detour_travel_time_minutes": detour_time_min,
                "affected_geometry_available": bool(has_geometry),
                "alternate_route_available": alt_route_avail,
                "alternate_route_valid": alt_route_val,
                "original_route_time_seconds": original_route_time_seconds,
                "alternate_route_time_seconds": alt_time_sec,
                "detour_seconds": det_sec,
                "incident_delay_seconds": inc_delay_sec,
                "detour_display": det_disp,
                "causal_status": causal_status,
            })

        # 4. Return aggregated result
        if not valid_incidents:
            return ContextProviderResult(
                source_name="Road Restrictions",
                status=DataSourceStatus.AVAILABLE,
                impact_minutes=0,
                description="No active road closures or restrictions along transit corridor — direct route confirmed. Source: TomTom Traffic Incidents (REAL).",
                sampled_at=now,
                category="ROAD",
                provenance="REAL",
                freshness="FRESH",
                impact_classification="NOT_APPLIED",
                causal_status="NOT_RELEVANT",
                affected_geometry_available=False,
                alternate_route_available=False,
                alternate_route_valid=False,
                detour_seconds=None,
                incident_delay_seconds=None,
                detour_display=None,
                fetched_timestamp=now.isoformat(),
                corridor_buffer_meters=STRICT_ROAD_CORRIDOR_BUFFER_METERS,
                restriction_count=0,
                is_route_relevant=False,
                relevance_status="NOT_RELEVANT",
                relevance_reason="No incidents detected along route corridor",
                applied_to_eta=False,
                distance_to_route=None,
                evaluated_items=[],
            )

        # Select the authoritative route-relevant incident (Step 2 & Step 6)
        route_relevant_incidents = [x for x in valid_incidents if x.get("is_route_relevant", False)]
        if route_relevant_incidents:
            route_relevant_incidents.sort(
                key=lambda x: (
                    x.get("applied_to_eta", False),
                    (x.get("detour_seconds") or 0) > 0,
                    (x.get("incident_delay_seconds") or 0) > 0,
                    (x.get("delay_min") or 0) > 0,
                    x.get("is_closed", False),
                    x.get("magnitude", 0),
                ),
                reverse=True,
            )
            primary = route_relevant_incidents[0]
            total_delay = primary.get("impact_minutes", 0)
            detour_seconds = primary.get("detour_seconds")
            incident_delay_seconds = primary.get("incident_delay_seconds")
            primary_classification = primary.get("impact_classification", "NOT_APPLIED")
            primary_causal_status = primary.get("causal_status", "NOT_RELEVANT")
            alt_time_sec = primary.get("alternate_route_time_seconds")
            alt_route_avail = primary.get("alternate_route_available", False)
            alt_route_val = primary.get("alternate_route_valid", False)
            primary_detour_display = primary.get("detour_display") or (_format_detour_evidence(detour_seconds) if detour_seconds is not None and detour_seconds > 0 else None)
        else:
            primary = valid_incidents[0]
            total_delay = 0
            detour_seconds = None
            incident_delay_seconds = None
            primary_classification = "NOT_APPLIED"
            primary_causal_status = "NOT_RELEVANT"
            primary_detour_display = None
            alt_time_sec = None
            alt_route_avail = False
            alt_route_val = False

        if total_delay > 0:
            if detour_seconds is not None and detour_seconds > 0 and alt_route_avail:
                orig_m = round(original_route_time_seconds / 60.0) if original_route_time_seconds else None
                alt_m = round(alt_time_sec / 60.0) if alt_time_sec else None
                comparison_str = (
                    f"Alternate route: {alt_m} min vs original {orig_m} min (+{total_delay} min). "
                    if (alt_m is not None and orig_m is not None)
                    else ""
                )
                description = (
                    f"Route-relevant road restriction ({primary['road_name']}: {primary['desc_summary']}) adds +{total_delay} min detour delay. "
                    f"{comparison_str}Derived from alternate route comparison. Source: TomTom Traffic Incidents (REAL)."
                )
            elif incident_delay_seconds is not None and incident_delay_seconds > 0:
                inc_str = _format_incident_delay_evidence(incident_delay_seconds)
                description = (
                    f"Route-relevant road restriction ({primary['road_name']}: {primary['desc_summary']}) adds +{total_delay} min incident delay. "
                    f"TomTom reported incident delay: {inc_str}. Source: TomTom Traffic Incidents (REAL)."
                )
            else:
                description = (
                    f"Route-relevant road restriction ({primary['road_name']}: {primary['desc_summary']}) adds +{total_delay} min delay. "
                    f"Source: TomTom Traffic Incidents (REAL)."
                )
        else:
            relevant_count = len(route_relevant_incidents)
            if primary.get("freshness") == "STALE":
                description = (
                    f"Road restriction ({primary['road_name']}) data is stale; ETA impact not applied — 0 min delay applied. "
                    f"Source: TomTom Traffic Incidents (REAL / STALE)."
                )
            elif relevant_count > 0:
                if primary_causal_status == "UNAVAILABLE":
                    description = (
                        f"Restriction detected ({primary['road_name']}), but no verified alternate-route detour could be calculated. "
                        f"Source: TomTom Traffic Incidents (REAL)."
                    )
                elif primary_causal_status == "INCLUDED_IN_LIVE_ROUTE" or (traffic_delay_seconds is not None and traffic_delay_seconds > 0):
                    description = (
                        f"{relevant_count} road incident{'s' if relevant_count > 1 else ''} on route ({primary['road_name']}: {primary['desc_summary']}) — slowdown already accounted for in live route traffic (0 min extra delay applied). "
                        f"Source: TomTom Traffic Incidents (REAL)."
                    )
                elif detour_seconds is not None and detour_seconds > 0 and alt_route_avail:
                    orig_m = round(original_route_time_seconds / 60.0) if original_route_time_seconds else None
                    alt_m = round(alt_time_sec / 60.0) if alt_time_sec else None
                    det_evidence = primary_detour_display or f"{detour_seconds} sec additional (<1 min)"
                    comparison_str = (
                        f"Alternate route: {alt_m} min vs original {orig_m} min (+{detour_seconds}s, <1 min). "
                        if (alt_m is not None and orig_m is not None)
                        else ""
                    )
                    description = (
                        f"Route-relevant road restriction ({primary['road_name']}: {primary['desc_summary']}) adds {det_evidence}. "
                        f"{comparison_str}Derived from alternate route comparison. Source: TomTom Traffic Incidents (REAL)."
                    )
                elif primary.get("is_closed"):
                    description = (
                        f"Route-relevant restriction detected ({primary['road_name']}) — no additional detour time measured. "
                        f"Source: TomTom Traffic Incidents (REAL)."
                    )
                else:
                    description = (
                        f"Road incident on route ({primary['road_name']}: {primary['desc_summary']}) has minor/informational impact — 0 min delay applied. "
                        f"Source: TomTom Traffic Incidents (REAL)."
                    )
            else:
                description = (
                    f"{len(valid_incidents)} road incident{'s' if len(valid_incidents) != 1 else ''} "
                    f"detected near area, but none affect the selected route corridor (not affecting this route, Route relevance: NOT RELEVANT) — 0 min delay applied. "
                    f"Source: TomTom Traffic Incidents (REAL)."
                )

        return ContextProviderResult(
            source_name="Road Restrictions",
            status=DataSourceStatus.AVAILABLE,
            impact_minutes=total_delay,
            description=description,
            sampled_at=now,
            category="ROAD",
            provenance="REAL",
            freshness=primary.get("freshness", "FRESH"),
            impact_classification=primary_classification,
            causal_status=primary_causal_status,
            affected_geometry_available=primary.get("affected_geometry_available"),
            alternate_route_available=alt_route_avail,
            alternate_route_valid=alt_route_val,
            original_route_time_seconds=original_route_time_seconds,
            alternate_route_time_seconds=alt_time_sec,
            detour_seconds=detour_seconds,
            incident_delay_seconds=incident_delay_seconds,
            detour_display=primary_detour_display,
            provider_timestamp=primary.get("start"),
            fetched_timestamp=now.isoformat(),
            restriction_count=len(valid_incidents),
            active_restriction_name=primary["road_name"],
            restriction_category=primary["category_name"],
            restriction_severity=primary["severity_name"],
            restriction_id=primary["id"],
            restriction_start=primary.get("start"),
            restriction_end=primary.get("end"),
            restriction_road_name=primary["road_name"],
            restriction_delay_seconds=primary.get("delay_sec"),
            restriction_distance_miles=primary.get("dist_mi"),
            is_road_closed=primary["is_closed"],
            is_route_relevant=primary.get("is_route_relevant", False),
            relevance_status=primary.get("relevance_status", "NOT_RELEVANT"),
            relevance_reason=primary.get("relevance_reason"),
            applied_to_eta=total_delay > 0,
            corridor_buffer_meters=STRICT_ROAD_CORRIDOR_BUFFER_METERS,
            distance_to_route=primary.get("distance_to_route"),
            distance_to_route_meters=primary.get("distance_to_route_meters"),
            distance_to_route_km=primary.get("distance_to_route_km"),
            distance_to_route_display=primary.get("distance_to_route_display"),
            detour_travel_time_minutes=primary.get("detour_travel_time_minutes"),
            evaluated_items=valid_incidents,
        )


# ── Provider Registry ───────────────────────────────────────────────────────────

def build_provider_pipeline() -> list[BaseContextProvider]:
    """
    Returns the ordered list of context providers used by the ETA engine.
    GPS and Weather are evaluated first; traffic/events/road last.
    """
    return [
        GPSLocationProvider(),
        WeatherProvider(),
        TrafficDataProvider(),
        EventsDataProvider(),
        RoadRestrictionProvider(),
    ]
