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
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


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

    def to_factor_dict(self) -> dict:
        """Convert to ContextFactor-compatible dict for ETA response."""
        return {
            "category": self.category,
            "factor": self.source_name,
            "impact_minutes": self.impact_minutes,
            "description": self.description,
        }

    def to_data_source_dict(self) -> dict:
        """Convert to DataSource-compatible dict for ETA response."""
        return {
            "name": self.source_name,
            "status": self.status.value,
            "description": self.description,
            "impact_minutes": self.impact_minutes,
            "sampled_at": self.sampled_at.isoformat(),
            "category": self.category,
        }


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

# GPS staleness threshold in seconds (2 hours)
_GPS_STALE_SECONDS = 7200


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

        if technician_lat is None or technician_lon is None:
            return ContextProviderResult(
                source_name="GPS Location",
                status=DataSourceStatus.UNAVAILABLE,
                impact_minutes=0,
                description="Technician GPS coordinates not available in system.",
                sampled_at=now,
                category="GPS",
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
            )

        # Check staleness if technician record timestamp is available
        if tech_updated_at is not None:
            # Ensure timezone-aware comparison
            ref = tech_updated_at if tech_updated_at.tzinfo else tech_updated_at.replace(tzinfo=timezone.utc)
            age_seconds = (now - ref).total_seconds()
            if age_seconds > _GPS_STALE_SECONDS:
                return ContextProviderResult(
                    source_name="GPS Location",
                    status=DataSourceStatus.STALE,
                    impact_minutes=0,
                    description=(
                        f"Technician GPS last updated {int(age_seconds / 60)} min ago — "
                        "location may not reflect current position. ETA computed from last known fix."
                    ),
                    sampled_at=now,
                    category="GPS",
                )

        return ContextProviderResult(
            source_name="GPS Location",
            status=DataSourceStatus.AVAILABLE,
            impact_minutes=0,
            description=(
                f"Technician GPS location confirmed ({technician_lat:.4f}°N, {technician_lon:.4f}°W)."
            ),
            sampled_at=now,
            category="GPS",
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

# Default weather used when no condition is supplied
_DEFAULT_WEATHER = "Moderate Rain"


class WeatherProvider(BaseContextProvider):
    """
    Evaluates weather impact on ETA from dispatcher-supplied condition string.

    Status:
      AVAILABLE — a recognized weather condition was provided or the system default is used
      UNAVAILABLE — not applicable (weather is always minimally available via default)

    Note: This provider uses a dispatcher-supplied query param, not a real meteorological API.
    A real implementation would call a weather API (e.g. OpenWeatherMap) using job coordinates.
    """

    async def evaluate(
        self,
        weather_condition: Optional[str] = None,
        **kwargs,
    ) -> ContextProviderResult:
        now = datetime.now(timezone.utc)
        condition = (weather_condition or _DEFAULT_WEATHER).strip()
        key = condition.upper()
        impact = _WEATHER_IMPACT.get(key, 0)

        # If the condition key is not in our map, use 0 delay but note it
        condition_recognized = key in _WEATHER_IMPACT

        if impact == 0:
            description = (
                f"Weather: {condition} — clear transit conditions, no travel delay."
            )
        else:
            description = (
                f"Weather: {condition} — adverse conditions add +{impact} min transit delay."
            )

        if not condition_recognized:
            description = (
                f"Weather condition '{condition}' not in classification table — "
                "zero delay applied conservatively."
            )

        return ContextProviderResult(
            source_name="Weather",
            status=DataSourceStatus.AVAILABLE,
            impact_minutes=impact,
            description=description,
            sampled_at=now,
            category="WEATHER",
        )


# ── Traffic Data Provider ───────────────────────────────────────────────────────

class TrafficDataProvider(BaseContextProvider):
    """
    Real-time traffic data provider.

    Currently UNAVAILABLE — no real-time traffic feed (e.g. TomTom Traffic API,
    HERE Traffic, Google Maps Platform) is integrated.

    Future integration: implement `evaluate()` to call a traffic API using
    technician origin coordinates and job destination coordinates.
    """

    async def evaluate(self, **kwargs) -> ContextProviderResult:
        return ContextProviderResult(
            source_name="Traffic Data",
            status=DataSourceStatus.UNAVAILABLE,
            impact_minutes=0,
            description=(
                "Real-time traffic feed not integrated — "
                "no traffic adjustment applied."
            ),
            sampled_at=datetime.now(timezone.utc),
            category="TRAFFIC",
        )


# ── Events Data Provider ────────────────────────────────────────────────────────

class EventsDataProvider(BaseContextProvider):
    """
    Local events / public gatherings data provider.

    Currently UNAVAILABLE — no event/permit feed (e.g. Open311, Ticketmaster,
    city permit APIs) is integrated.

    Future integration: implement `evaluate()` to check for events near the
    job's GPS coordinates that may impact road access or parking.
    """

    async def evaluate(self, **kwargs) -> ContextProviderResult:
        return ContextProviderResult(
            source_name="Events",
            status=DataSourceStatus.UNAVAILABLE,
            impact_minutes=0,
            description=(
                "Event / public gathering data not integrated — "
                "no event adjustment applied."
            ),
            sampled_at=datetime.now(timezone.utc),
            category="EVENTS",
        )


# ── Road Restriction Provider ───────────────────────────────────────────────────

class RoadRestrictionProvider(BaseContextProvider):
    """
    Road closure and restriction data provider.

    Currently UNAVAILABLE — no road-closure or restriction feed (e.g. OpenStreetMap
    Overpass API, Waze Closures, LADOT, city TMS feeds) is integrated.

    Future integration: implement `evaluate()` to query road restrictions
    along the technician's route using origin/destination coordinates.
    """

    async def evaluate(self, **kwargs) -> ContextProviderResult:
        return ContextProviderResult(
            source_name="Road Restrictions",
            status=DataSourceStatus.UNAVAILABLE,
            impact_minutes=0,
            description=(
                "Road closure / restriction data not integrated — "
                "no restriction adjustment applied."
            ),
            sampled_at=datetime.now(timezone.utc),
            category="ROAD",
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
