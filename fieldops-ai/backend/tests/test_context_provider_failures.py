"""
Focused Context Provider Failure & Resilience Tests — Module 20.

Verifies that context providers handle network timeouts, missing credentials,
expired feeds, malformed payloads, and provider outages gracefully without throwing
unhandled exceptions, ensuring non-AVAILABLE inputs strictly contribute 0 minutes impact.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import settings
from app.services.context_aggregation import ContextAggregationService
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    EventsDataProvider,
    GPSLocationProvider,
    RoadRestrictionProvider,
    TrafficDataProvider,
    WeatherProvider,
)


@pytest.mark.asyncio
async def test_traffic_provider_unavailable_http_error():
    """Verify HTTP error (e.g. 503 Service Unavailable) returns UNAVAILABLE with 0 impact."""
    provider = TrafficDataProvider()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(503, text="Service Unavailable")
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194, dest_lat=37.7833, dest_lon=-122.4167
        )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert "HTTP 503" in res.description or "Fallback" in res.description


@pytest.mark.asyncio
async def test_traffic_provider_timeout():
    """Verify network timeout during traffic request returns UNAVAILABLE with 0 impact."""
    provider = TrafficDataProvider()

    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Network timeout")):
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194, dest_lat=37.7833, dest_lon=-122.4167
        )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert "timed out" in res.description


@pytest.mark.asyncio
async def test_traffic_provider_credentials_missing(monkeypatch):
    """Verify TomTom provider returns UNAVAILABLE when API key is missing."""
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "tomtom")
    monkeypatch.setattr(settings, "TRAFFIC_API_KEY", None)

    provider = TrafficDataProvider()
    res = await provider.evaluate(
        origin_lat=37.7749, origin_lon=-122.4194, dest_lat=37.7833, dest_lon=-122.4167
    )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert "API key" in res.description


@pytest.mark.asyncio
async def test_traffic_provider_invalid_response():
    """Verify malformed API response (missing routes) returns INVALID/UNAVAILABLE with 0 impact."""
    provider = TrafficDataProvider()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json={"code": "Error", "message": "No route found"})
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194, dest_lat=37.7833, dest_lon=-122.4167
        )

    assert res.status in (DataSourceStatus.INVALID, DataSourceStatus.UNAVAILABLE)
    assert res.impact_minutes == 0


@pytest.mark.asyncio
async def test_event_provider_unavailable_when_no_credentials(monkeypatch):
    """Verify event provider returns UNAVAILABLE with 0 impact when no feed or key is present."""
    monkeypatch.setattr(settings, "EVENTS_API_KEY", None)
    provider = EventsDataProvider()
    res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert "not integrated" in res.description or "key missing" in res.description


@pytest.mark.asyncio
async def test_event_provider_expired_event_filtered():
    """Verify expired events (end_time in past) are filtered out and contribute 0 delay."""
    provider = EventsDataProvider()
    past_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()

    expired_feed = [
        {
            "id": "EVT-101",
            "name": "Past Marathon",
            "end_time": past_time,
            "latitude": 37.7749,
            "longitude": -122.4194,
            "impact_minutes": 15,
        }
    ]

    res = await provider.evaluate(
        dest_lat=37.7749, dest_lon=-122.4194, events_feed=expired_feed
    )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.impact_minutes == 0
    assert "No active public events" in res.description


@pytest.mark.asyncio
async def test_road_closure_provider_unavailable_when_no_credentials():
    """Verify road restriction provider returns UNAVAILABLE with 0 impact when no feed is present."""
    provider = RoadRestrictionProvider()
    res = await provider.evaluate(
        origin_lat=37.7749, origin_lon=-122.4194, dest_lat=37.7833, dest_lon=-122.4167
    )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert "not integrated" in res.description or "key missing" in res.description


@pytest.mark.asyncio
async def test_road_closure_provider_stale_expired_filtered():
    """Verify expired road closures (expires_at in past) are ignored with 0 delay."""
    provider = RoadRestrictionProvider()
    past_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    stale_closures = [
        {
            "id": "CLOSURE-99",
            "road_name": "Main Street",
            "expires_at": past_time,
            "latitude": 37.7750,
            "longitude": -122.4190,
            "impact_minutes": 20,
        }
    ]

    res = await provider.evaluate(
        origin_lat=37.7749,
        origin_lon=-122.4194,
        dest_lat=37.7833,
        dest_lon=-122.4167,
        restrictions_feed=stale_closures,
    )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.impact_minutes == 0
    assert "No active road closures" in res.description


@pytest.mark.asyncio
async def test_multi_provider_failure_isolation():
    """
    Verify that when one provider times out (Traffic), other valid providers (Weather)
    continue to contribute their impact without crashing the context aggregation layer.
    """
    aggregator = ContextAggregationService()

    # Weather succeeds (AVAILABLE, +10 min impact)
    weather_res = ContextProviderResult(
        source_name="Weather Data",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=10,
        description="Heavy rain adds +10 min delay.",
        category="WEATHER",
    )

    # Traffic times out (UNAVAILABLE, 0 min impact)
    traffic_res = ContextProviderResult(
        source_name="Traffic Data",
        status=DataSourceStatus.UNAVAILABLE,
        impact_minutes=0,
        description="Traffic API request timed out.",
        category="TRAFFIC",
    )

    # Events unavailable (UNAVAILABLE, 0 min impact)
    events_res = ContextProviderResult(
        source_name="Events",
        status=DataSourceStatus.UNAVAILABLE,
        impact_minutes=0,
        description="Events feed not integrated.",
        category="EVENTS",
    )

    summary = aggregator.aggregate(
        provider_results=[weather_res, traffic_res, events_res],
        baseline_eta_minutes=15,
        distance_km=8.0,
        distance_miles=5.0,
    )

    assert summary.total_adjustment_minutes == 10
    assert summary.available_count == 1
    assert summary.unavailable_count == 2
    assert summary.calculation_status == "PARTIAL"


@pytest.mark.asyncio
async def test_zero_fake_eta_impact_when_all_context_unavailable():
    """Verify that when all external providers return UNAVAILABLE, total adjustment is exactly 0."""
    aggregator = ContextAggregationService()

    results = [
        ContextProviderResult(
            source_name="GPS Location",
            status=DataSourceStatus.UNAVAILABLE,
            impact_minutes=0,
            description="No GPS fix",
            category="GPS",
        ),
        ContextProviderResult(
            source_name="Weather",
            status=DataSourceStatus.UNAVAILABLE,
            impact_minutes=0,
            description="Weather feed unavailable",
            category="WEATHER",
        ),
        ContextProviderResult(
            source_name="Traffic",
            status=DataSourceStatus.UNAVAILABLE,
            impact_minutes=0,
            description="Traffic feed unavailable",
            category="TRAFFIC",
        ),
    ]

    summary = aggregator.aggregate(
        provider_results=results,
        baseline_eta_minutes=20,
        distance_km=10.0,
        distance_miles=6.2,
    )

    assert summary.total_adjustment_minutes == 0
    assert summary.unavailable_count == 3
    assert summary.calculation_status == "INSUFFICIENT"
