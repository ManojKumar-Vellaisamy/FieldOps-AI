"""
Module 24 — Real Context Data Runtime Tests.

Verifies:
1. ContextProviderResult carries correct provenance field
2. OSRM provider returns provenance=DERIVED
3. Open-Meteo provider returns provenance=REAL when successful
4. TomTom provider returns provenance=UNAVAILABLE when API key missing
5. GPS provider returns provenance=SYSTEM
6. Events provider returns provenance=UNAVAILABLE when no feed configured
7. Road provider returns provenance=UNAVAILABLE when no feed configured
8. Provenance flows through to_data_source_dict()
9. ContextAggregationService correctly propagates provenance in DataSource
10. Weather provider uses technician location (lat/lon) over destination
11. All failure scenarios maintain 0 impact and UNAVAILABLE provenance
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import httpx

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
from app.core.config import settings


# -----------------------------------------------------------------------------
# 1. ContextProviderResult provenance field defaults
# -----------------------------------------------------------------------------

def test_context_provider_result_has_provenance_field():
    """ContextProviderResult must have a provenance field defaulting to UNAVAILABLE."""
    result = ContextProviderResult(
        source_name="Test Source",
        status=DataSourceStatus.UNAVAILABLE,
        impact_minutes=0,
        description="Test",
        category="TEST",
    )
    assert hasattr(result, "provenance")
    assert result.provenance == "UNAVAILABLE"


def test_context_provider_result_to_data_source_dict_includes_provenance():
    """to_data_source_dict() must include the provenance key."""
    result = ContextProviderResult(
        source_name="Test Source",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=5,
        description="Test",
        category="TEST",
        provenance="REAL",
    )
    d = result.to_data_source_dict()
    assert "provenance" in d
    assert d["provenance"] == "REAL"


# -----------------------------------------------------------------------------
# 2. GPS Provider provenance
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gps_provider_available_provenance_is_system():
    """GPSLocationProvider with valid coords must return provenance=SYSTEM."""
    provider = GPSLocationProvider()
    res = await provider.evaluate(technician_lat=37.7749, technician_lon=-122.4194)
    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "SYSTEM"


@pytest.mark.asyncio
async def test_gps_provider_unavailable_provenance_is_unavailable():
    """GPSLocationProvider with no coords must return provenance=UNAVAILABLE."""
    provider = GPSLocationProvider()
    res = await provider.evaluate(technician_lat=None, technician_lon=None)
    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_gps_provider_stale_provenance_is_system():
    """GPSLocationProvider with stale coords returns provenance=SYSTEM."""
    provider = GPSLocationProvider()
    old_time = datetime.now(timezone.utc) - timedelta(hours=4)
    res = await provider.evaluate(
        technician_lat=37.7749,
        technician_lon=-122.4194,
        tech_updated_at=old_time,
    )
    assert res.status == DataSourceStatus.STALE
    assert res.provenance == "SYSTEM"


@pytest.mark.asyncio
async def test_gps_provider_invalid_coords_provenance_is_unavailable():
    """GPSLocationProvider with out-of-bounds coords returns provenance=UNAVAILABLE."""
    provider = GPSLocationProvider()
    res = await provider.evaluate(technician_lat=120.0, technician_lon=-200.0)
    assert res.status == DataSourceStatus.INVALID
    assert res.provenance == "UNAVAILABLE"


# -----------------------------------------------------------------------------
# 3. Weather Provider provenance
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weather_provider_open_meteo_success_provenance_is_real():
    """WeatherProvider must return provenance=REAL when Open-Meteo API responds successfully."""
    provider = WeatherProvider()
    mock_response = {"current_weather": {"weathercode": 63, "temperature": 18.5}}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_response)
        res = await provider.evaluate(lat=37.7749, lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert "Open-Meteo" in res.source_name


@pytest.mark.asyncio
async def test_weather_provider_fallback_condition_provenance_is_derived():
    """WeatherProvider fallback (condition string) returns provenance=DERIVED."""
    provider = WeatherProvider()
    res = await provider.evaluate(weather_condition="Clear")
    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "DERIVED"


@pytest.mark.asyncio
async def test_weather_provider_uses_technician_location_first():
    """WeatherProvider must query Open-Meteo at technician location (lat/lon), not destination."""
    provider = WeatherProvider()
    mock_response = {"current_weather": {"weathercode": 0, "temperature": 22.0}}
    called_url = []

    async def capture_get(url, **kwargs):
        called_url.append(url)
        return httpx.Response(200, json=mock_response)

    with patch("httpx.AsyncClient.get", side_effect=capture_get):
        await provider.evaluate(
            lat=10.0,
            lon=20.0,
            dest_lat=37.7749,
            dest_lon=-122.4194,
        )

    assert len(called_url) > 0
    assert "latitude=10.0" in called_url[0]
    assert "longitude=20.0" in called_url[0]


@pytest.mark.asyncio
async def test_weather_provider_timeout_falls_back_to_derived():
    """When Open-Meteo times out, WeatherProvider falls back and returns provenance=DERIVED."""
    provider = WeatherProvider()
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
        res = await provider.evaluate(lat=37.7749, lon=-122.4194)
    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "DERIVED"


# -----------------------------------------------------------------------------
# 4. Traffic Provider (OSRM) provenance
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_osrm_traffic_provider_provenance_is_derived(monkeypatch):
    """OSRM TrafficDataProvider must return provenance=DERIVED (routing engine, not live traffic)."""
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "osrm")
    provider = TrafficDataProvider()
    mock_osrm = {"code": "Ok", "routes": [{"duration": 900.0, "distance": 12000.0}]}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_osrm)
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.8049, dest_lon=-122.4094,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "DERIVED"


@pytest.mark.asyncio
async def test_osrm_is_never_labeled_real(monkeypatch):
    """OSRM result must NEVER have provenance=REAL. It is routing data, not live traffic."""
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "osrm")
    provider = TrafficDataProvider()
    mock_osrm = {"code": "Ok", "routes": [{"duration": 1200.0, "distance": 15000.0}]}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_osrm)
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.8049, dest_lon=-122.4094,
        )

    assert res.provenance != "REAL", "OSRM must never be classified as REAL traffic"


@pytest.mark.asyncio
async def test_osrm_timeout_provenance_is_unavailable():
    """OSRM timeout must return provenance=UNAVAILABLE and 0 impact."""
    provider = TrafficDataProvider()
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.8049, dest_lon=-122.4094,
        )
    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert res.provenance == "UNAVAILABLE"


# -----------------------------------------------------------------------------
# 5. TomTom Provider provenance
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_no_key_provenance_is_unavailable(monkeypatch):
    """TomTom TrafficDataProvider must return provenance=UNAVAILABLE when API key is missing."""
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "tomtom")
    monkeypatch.setattr(settings, "TRAFFIC_API_KEY", None)

    provider = TrafficDataProvider()
    res = await provider.evaluate(
        origin_lat=37.7749, origin_lon=-122.4194,
        dest_lat=37.8049, dest_lon=-122.4094,
    )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert res.provenance == "UNAVAILABLE"
    assert "API key" in res.description


@pytest.mark.asyncio
async def test_tomtom_with_key_provenance_is_real(monkeypatch):
    """TomTom with valid API key and successful response returns provenance=REAL."""
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "tomtom")
    monkeypatch.setattr(settings, "TRAFFIC_API_KEY", "test-key-123")

    mock_tomtom = {
        "routes": [{"summary": {
            "travelTimeInSeconds": 1800,
            "noTrafficTravelTimeInSeconds": 1200,
        }}]
    }

    provider = TrafficDataProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_tomtom)
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.8049, dest_lon=-122.4094,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 10  # 30m - 20m = 10m delay


# -----------------------------------------------------------------------------
# 6. Events Provider provenance
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_events_provider_no_feed_provenance_is_unavailable():
    """EventsDataProvider with no feed returns provenance=UNAVAILABLE."""
    provider = EventsDataProvider()
    res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)
    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert res.provenance == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_events_provider_real_feed_provenance_is_real():
    """EventsDataProvider with real feed (even with 0 active events) returns provenance=REAL."""
    provider = EventsDataProvider()
    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    feed = [{
        "id": "EVT-EXPIRED", "name": "Expired Marathon",
        "end_time": past_time,
        "latitude": 37.7749, "longitude": -122.4194,
        "impact_minutes": 15,
    }]
    res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194, events_feed=feed)
    assert res.status == DataSourceStatus.AVAILABLE
    assert res.impact_minutes == 0
    assert res.provenance == "REAL"


# -----------------------------------------------------------------------------
# 7. Road Provider provenance
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_road_provider_no_feed_provenance_is_unavailable():
    """RoadRestrictionProvider with no feed returns provenance=UNAVAILABLE."""
    provider = RoadRestrictionProvider()
    res = await provider.evaluate(
        origin_lat=37.7749, origin_lon=-122.4194,
        dest_lat=37.7833, dest_lon=-122.4167,
    )
    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert res.provenance == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_road_provider_expired_closures_provenance_is_real():
    """RoadRestrictionProvider with expired closures returns provenance=REAL with 0 impact."""
    provider = RoadRestrictionProvider()
    past_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    feed = [{
        "id": "CLOSURE-EXPIRED", "road_name": "Main St",
        "expires_at": past_time,
        "latitude": 37.7750, "longitude": -122.4190,
        "impact_minutes": 20,
    }]
    res = await provider.evaluate(
        origin_lat=37.7749, origin_lon=-122.4194,
        dest_lat=37.7833, dest_lon=-122.4167,
        restrictions_feed=feed,
    )
    assert res.status == DataSourceStatus.AVAILABLE
    assert res.impact_minutes == 0
    assert res.provenance == "REAL"


# -----------------------------------------------------------------------------
# 8. Context Aggregation preserves provenance
# -----------------------------------------------------------------------------

def test_context_aggregation_preserves_provenance():
    """ContextAggregationService must propagate provenance from results to DataSource dicts."""
    weather = ContextProviderResult(
        source_name="Weather Data (Open-Meteo API)",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=8, description="Heavy rain",
        category="WEATHER", provenance="REAL",
    )
    osrm = ContextProviderResult(
        source_name="Route Baseline (OSRM)",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=3, description="Routing baseline",
        category="TRAFFIC", provenance="DERIVED",
    )
    events = ContextProviderResult(
        source_name="Events",
        status=DataSourceStatus.UNAVAILABLE,
        impact_minutes=0, description="No feed",
        category="EVENTS", provenance="UNAVAILABLE",
    )

    agg = ContextAggregationService()
    summary = agg.aggregate(
        provider_results=[weather, osrm, events],
        baseline_eta_minutes=20,
        distance_km=10.0,
        distance_miles=6.2,
    )

    ds_map = {ds.name: ds for ds in summary.data_sources}
    assert ds_map["Weather Data (Open-Meteo API)"].provenance == "REAL"
    assert ds_map["Route Baseline (OSRM)"].provenance == "DERIVED"
    assert ds_map["Events"].provenance == "UNAVAILABLE"


# -----------------------------------------------------------------------------
# 9. All providers UNAVAILABLE — zero total adjustment
# -----------------------------------------------------------------------------

def test_all_providers_unavailable_adjustment_is_zero():
    """When all providers are UNAVAILABLE, total adjustment must be exactly 0."""
    results = [
        ContextProviderResult("GPS", DataSourceStatus.UNAVAILABLE, 0, "No GPS", category="GPS", provenance="UNAVAILABLE"),
        ContextProviderResult("Weather", DataSourceStatus.UNAVAILABLE, 0, "No weather", category="WEATHER", provenance="UNAVAILABLE"),
        ContextProviderResult("Traffic", DataSourceStatus.UNAVAILABLE, 0, "No traffic", category="TRAFFIC", provenance="UNAVAILABLE"),
        ContextProviderResult("Events", DataSourceStatus.UNAVAILABLE, 0, "No events", category="EVENTS", provenance="UNAVAILABLE"),
        ContextProviderResult("Road", DataSourceStatus.UNAVAILABLE, 0, "No road", category="ROAD", provenance="UNAVAILABLE"),
    ]

    agg = ContextAggregationService()
    summary = agg.aggregate(
        provider_results=results,
        baseline_eta_minutes=15,
        distance_km=8.0,
        distance_miles=5.0,
    )

    assert summary.total_adjustment_minutes == 0
    assert summary.unavailable_count == 5
    assert summary.calculation_status == "INSUFFICIENT"
