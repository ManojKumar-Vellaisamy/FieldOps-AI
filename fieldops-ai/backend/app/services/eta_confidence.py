"""
ETA Confidence & Reliability Engine — Phase 4G.

Evaluates the actual health, freshness, provenance, and availability of ETA data sources
to produce a truthful categorical reliability assessment:
  - HIGH
  - MEDIUM
  - LOW
  - DEGRADED
  - UNAVAILABLE

Strictly avoids fabricated percentage scores (no 98%, 95%, 0.95, etc.).
Provides transparent, deterministic operational explanations of why confidence
was assigned or degraded.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.services.context_providers import ContextProviderResult, DataSourceStatus


@dataclass
class ETAConfidenceAssessment:
    """Structured assessment of ETA reliability and source health."""

    confidence_level: str
    """Categorical reliability: HIGH | MEDIUM | LOW | DEGRADED | UNAVAILABLE"""

    confidence_reason: str
    """Deterministic, transparent explanation of reliability and degradation causes"""

    reliability_status: str
    """Operational reliability status matching confidence_level"""

    fresh_sources: list[str] = field(default_factory=list)
    """Sources verified fresh with current telemetry"""

    stale_sources: list[str] = field(default_factory=list)
    """Sources with stale telemetry exceeding operational freshness thresholds"""

    unavailable_sources: list[str] = field(default_factory=list)
    """Optional or critical sources that are unreachable or unconfigured"""

    degraded_sources: list[str] = field(default_factory=list)
    """Sources operating in derived/fallback mode or with reduced telemetry"""


class ETAConfidenceEngine:
    """
    Deterministic confidence evaluation engine.
    Analyzes critical prerequisites (technician GPS, routing baseline) and optional
    operational context (weather, events, road restrictions) to determine ETA reliability.
    """

    def evaluate(
        self,
        is_context_sufficient: bool,
        missing_context: Optional[list[str]] = None,
        gps_result: Optional[ContextProviderResult] = None,
        traffic_result: Optional[ContextProviderResult] = None,
        weather_result: Optional[ContextProviderResult] = None,
        events_result: Optional[ContextProviderResult] = None,
        road_result: Optional[ContextProviderResult] = None,
        has_authoritative_tomtom_route: bool = False,
        has_derived_osrm_route: bool = False,
        is_haversine_fallback: bool = False,
        detour_seconds: Optional[int] = None,
        detour_display: Optional[str] = None,
    ) -> ETAConfidenceAssessment:
        fresh_sources: list[str] = []
        stale_sources: list[str] = []
        unavailable_sources: list[str] = []
        degraded_sources: list[str] = []

        # ── 1. Evaluate GPS Location Source ──────────────────────────────────
        gps_is_fresh = False
        gps_is_stale = False
        gps_is_unknown = False

        if not gps_result or gps_result.status == DataSourceStatus.UNAVAILABLE:
            unavailable_sources.append("GPS Location")
        elif gps_result.freshness == "FRESH":
            gps_is_fresh = True
            fresh_sources.append("GPS Location")
        elif gps_result.freshness == "STALE" or gps_result.status == DataSourceStatus.STALE:
            gps_is_stale = True
            stale_sources.append("GPS Location")
        elif gps_result.freshness == "UNKNOWN":
            gps_is_unknown = True
            degraded_sources.append("GPS Location (Unverified Timestamp)")
        else:
            unavailable_sources.append("GPS Location")

        # ── 2. Evaluate Routing Baseline Source ──────────────────────────────
        if has_authoritative_tomtom_route:
            fresh_sources.append("TomTom Live Routing")
        elif has_derived_osrm_route:
            degraded_sources.append("OSRM Road Baseline (No Live Traffic)")
            unavailable_sources.append("Live Traffic")
        elif is_haversine_fallback:
            degraded_sources.append("Haversine Straight-Line Fallback")
            unavailable_sources.append("Road Routing")
            unavailable_sources.append("Live Traffic")
        else:
            unavailable_sources.append("Road Routing")

        # ── 3. Evaluate Optional Context Sources ─────────────────────────────
        # Weather
        weather_available = False
        if weather_result and weather_result.status == DataSourceStatus.AVAILABLE:
            if weather_result.freshness == "STALE":
                stale_sources.append("Weather (Open-Meteo)")
            else:
                weather_available = True
                fresh_sources.append("Weather (Open-Meteo)")
        else:
            unavailable_sources.append("Weather (Open-Meteo)")

        # Events
        events_available = False
        if events_result and events_result.status == DataSourceStatus.AVAILABLE:
            if events_result.freshness == "STALE":
                stale_sources.append("Events (PredictHQ)")
            else:
                events_available = True
                fresh_sources.append("Events (PredictHQ)")
        else:
            unavailable_sources.append("Events (PredictHQ)")

        # Road Restrictions
        road_available = False
        if road_result and road_result.status == DataSourceStatus.AVAILABLE:
            if road_result.freshness == "STALE":
                stale_sources.append("Road Restrictions (TomTom)")
            else:
                road_available = True
                fresh_sources.append("Road Restrictions (TomTom)")
        else:
            unavailable_sources.append("Road Restrictions (TomTom)")

        # ── 4. Deterministic Confidence Level Classification ─────────────────

        # CASE A: Missing critical context (Technician GPS coordinates or destination)
        if not is_context_sufficient or not gps_result or gps_result.status == DataSourceStatus.UNAVAILABLE:
            reason = (
                f"ETA unavailable: {missing_context[0]}"
                if (missing_context and len(missing_context) > 0)
                else "No valid technician position or route available."
            )
            return ETAConfidenceAssessment(
                confidence_level="UNAVAILABLE",
                confidence_reason=reason,
                reliability_status="UNAVAILABLE",
                fresh_sources=fresh_sources,
                stale_sources=stale_sources,
                unavailable_sources=unavailable_sources,
                degraded_sources=degraded_sources,
            )

        # CASE B: Haversine fallback active (Both TomTom and OSRM failed)
        if is_haversine_fallback or (not has_authoritative_tomtom_route and not has_derived_osrm_route):
            return ETAConfidenceAssessment(
                confidence_level="DEGRADED",
                confidence_reason=(
                    "TomTom and OSRM routing unavailable; Haversine straight-line baseline is being used. "
                    "Live road routing and traffic are unavailable."
                ),
                reliability_status="DEGRADED",
                fresh_sources=fresh_sources,
                stale_sources=stale_sources,
                unavailable_sources=unavailable_sources,
                degraded_sources=degraded_sources,
            )

        # CASE C: OSRM fallback active (TomTom unavailable, OSRM road baseline succeeded)
        # CRITICAL RULE: OSRM does not provide live traffic flow; confidence must be DEGRADED
        if has_derived_osrm_route:
            return ETAConfidenceAssessment(
                confidence_level="DEGRADED",
                confidence_reason=(
                    "TomTom unavailable; OSRM road baseline is being used. Live traffic is unavailable."
                ),
                reliability_status="DEGRADED",
                fresh_sources=fresh_sources,
                stale_sources=stale_sources,
                unavailable_sources=unavailable_sources,
                degraded_sources=degraded_sources,
            )

        # CASE D: Authoritative TomTom route with Stale GPS
        if gps_is_stale:
            reason = "GPS position is stale; ETA uses last known technician position."
            if not weather_available or not events_available or not road_available:
                unavail = []
                if not weather_available:
                    unavail.append("weather")
                if not events_available:
                    unavail.append("events")
                if not road_available:
                    unavail.append("road restrictions")
                reason += f" Context unavailable: {', '.join(unavail)}."

            return ETAConfidenceAssessment(
                confidence_level="LOW",
                confidence_reason=reason,
                reliability_status="LOW",
                fresh_sources=fresh_sources,
                stale_sources=stale_sources,
                unavailable_sources=unavailable_sources,
                degraded_sources=degraded_sources,
            )

        # CASE E: Authoritative TomTom route with UNKNOWN GPS timestamp (NULL timestamp)
        if gps_is_unknown:
            reason = "GPS observation timestamp unavailable; ETA calculated with unverified GPS freshness."
            return ETAConfidenceAssessment(
                confidence_level="LOW",
                confidence_reason=reason,
                reliability_status="LOW",
                fresh_sources=fresh_sources,
                stale_sources=stale_sources,
                unavailable_sources=unavailable_sources,
                degraded_sources=degraded_sources,
            )

        # CASE F: Authoritative TomTom route + Fresh GPS, but optional context is unavailable or stale
        optional_degraded = []
        if not weather_available:
            optional_degraded.append("weather")
        if not events_available:
            optional_degraded.append("events")
        if not road_available:
            optional_degraded.append("road restrictions")

        if optional_degraded:
            if len(optional_degraded) == 1:
                ctx_phrase = f"{optional_degraded[0]} context unavailable."
            elif len(optional_degraded) == 2:
                ctx_phrase = f"{optional_degraded[0]} and {optional_degraded[1]} context unavailable."
            else:
                ctx_phrase = f"{', '.join(optional_degraded[:-1])}, and {optional_degraded[-1]} context unavailable."

            reason = f"Authoritative route available; {ctx_phrase}"
            return ETAConfidenceAssessment(
                confidence_level="MEDIUM",
                confidence_reason=reason,
                reliability_status="MEDIUM",
                fresh_sources=fresh_sources,
                stale_sources=stale_sources,
                unavailable_sources=unavailable_sources,
                degraded_sources=degraded_sources,
            )

        # CASE G: Authoritative TomTom route + Fresh GPS + All evaluated context providers available
        if detour_seconds and detour_seconds > 0:
            detour_str = detour_display if detour_display else f"{detour_seconds}s detour"
            reason = (
                f"Fresh GPS and authoritative TomTom route available; verified road detour included ({detour_str})."
            )
        else:
            reason = "Fresh GPS and authoritative TomTom route available."

        return ETAConfidenceAssessment(
            confidence_level="HIGH",
            confidence_reason=reason,
            reliability_status="HIGH",
            fresh_sources=fresh_sources,
            stale_sources=stale_sources,
            unavailable_sources=unavailable_sources,
            degraded_sources=degraded_sources,
        )
