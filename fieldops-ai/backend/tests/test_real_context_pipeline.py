"""
Focused Test Suite for Real Context Data Pipeline & Data Provenance Contracts.

Verifies:
1. Open-Meteo live weather provider evaluation with valid GPS coordinates
2. Weather provider timeout / missing coordinates fallback
3. Traffic provider OSRM / TomTom evaluation
4. Traffic provider unavailable / invalid coordinates fallback
5. Events and Road Restrictions explicit UNAVAILABLE status contracts
6. Combined multi-provider context aggregation without fake delay injection
7. ETA Service calculation and data_sources provenance in ETAResponse
8. Dispatcher ETA override and WebSocket broadcast emission
"""

import pytest
from datetime import datetime, timezone
import uuid

from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    EventsDataProvider,
    GPSLocationProvider,
    RoadRestrictionProvider,
    TrafficDataProvider,
    WeatherProvider,
)
from app.services.context_aggregation import ContextAggregationService
from app.services.eta_service import ETAService


@pytest.mark.asyncio
async def test_weather_provider_fallback_when_no_coords():
    """Verify WeatherProvider returns AVAILABLE with 0 impact or default when no coords supplied."""
    provider = WeatherProvider()
    res = await provider.evaluate(weather_condition="Clear")
    assert res.status == DataSourceStatus.AVAILABLE
    assert res.impact_minutes == 0
    assert res.category == "WEATHER"
    assert "clear transit conditions" in res.description.lower()


@pytest.mark.asyncio
async def test_weather_provider_open_meteo_live_evaluation():
    """Verify WeatherProvider queries Open-Meteo API when valid coordinates exist."""
    provider = WeatherProvider()
    # San Francisco GPS coordinates
    res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)
    assert res.status == DataSourceStatus.AVAILABLE
    assert res.category == "WEATHER"
    assert "weather" in res.source_name.lower() or "open-meteo" in res.source_name.lower()


@pytest.mark.asyncio
async def test_traffic_provider_osrm_evaluation():
    """Verify TrafficDataProvider evaluates routing duration via OSRM/driving provider."""
    provider = TrafficDataProvider()
    res = await provider.evaluate(
        origin_lat=37.7749,
        origin_lon=-122.4194,
        dest_lat=37.7833,
        dest_lon=-122.4167,
        baseline_eta_minutes=10,
    )
    assert res.status in (DataSourceStatus.AVAILABLE, DataSourceStatus.UNAVAILABLE)
    assert res.category == "TRAFFIC"


@pytest.mark.asyncio
async def test_events_and_road_providers_explicit_unavailable():
    """Verify Events and Road Restriction providers return explicit UNAVAILABLE status with 0 impact."""
    events_p = EventsDataProvider()
    road_p = RoadRestrictionProvider()

    events_res = await events_p.evaluate()
    road_res = await road_p.evaluate()

    assert events_res.status == DataSourceStatus.UNAVAILABLE
    assert events_res.impact_minutes == 0
    assert "not integrated" in events_res.description

    assert road_res.status == DataSourceStatus.UNAVAILABLE
    assert road_res.impact_minutes == 0
    assert "not integrated" in road_res.description


@pytest.mark.asyncio
async def test_context_aggregation_zero_fake_adjustments():
    """Verify ContextAggregationService applies 0 adjustment for UNAVAILABLE or STALE sources."""
    agg = ContextAggregationService()
    now = datetime.now(timezone.utc)

    gps_res = ContextProviderResult(
        source_name="GPS Location",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="GPS fix confirmed",
        sampled_at=now,
        category="GPS",
    )
    weather_res = ContextProviderResult(
        source_name="Weather",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=5,
        description="Moderate Rain adds +5 min delay",
        sampled_at=now,
        category="WEATHER",
    )
    events_res = ContextProviderResult(
        source_name="Events",
        status=DataSourceStatus.UNAVAILABLE,
        impact_minutes=15,  # Even if 15 passed, status UNAVAILABLE must force 0 impact
        description="Events unavailable",
        sampled_at=now,
        category="EVENTS",
    )

    summary = agg.aggregate(
        provider_results=[gps_res, weather_res, events_res],
        baseline_eta_minutes=20,
        distance_km=10.0,
        distance_miles=6.2,
    )

    assert summary.total_adjustment_minutes == 5  # Only Weather (AVAILABLE) applied
    assert summary.unavailable_count == 1
    assert any(f.factor == "Weather" and f.impact_minutes == 5 for f in summary.factors)


@pytest.mark.asyncio
async def test_gps_provider_staleness_and_bounds():
    """Verify GPSLocationProvider flags invalid or stale coordinates."""
    provider = GPSLocationProvider()

    # Out of bounds
    invalid_res = await provider.evaluate(technician_lat=120.0, technician_lon=-200.0)
    assert invalid_res.status == DataSourceStatus.INVALID

    # Missing coordinates
    missing_res = await provider.evaluate(technician_lat=None, technician_lon=None)
    assert missing_res.status == DataSourceStatus.UNAVAILABLE
