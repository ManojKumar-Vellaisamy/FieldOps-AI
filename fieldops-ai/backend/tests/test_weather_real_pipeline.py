import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
import httpx
from httpx import Response
import uuid

from app.services.context_providers import WeatherProvider, DataSourceStatus
from app.services.eta_service import ETAService
from app.database.session import AsyncSessionLocal
from app.models.technician import Technician
from app.models.job import Job
from sqlalchemy import select


@pytest.mark.asyncio
async def test_real_precipitation_and_wind_parsing():
    """1. Verify real precipitation, wind speed, wind direction, and observation timestamp are parsed from Open-Meteo current schema."""
    provider = WeatherProvider()
    mock_payload = {
        "current": {
            "time": "2026-09-11T12:00",
            "interval": 900,
            "temperature_2m": 16.5,
            "precipitation": 2.5,
            "rain": 2.5,
            "weather_code": 61,  # Slight rain
            "wind_speed_10m": 18.2,
            "wind_direction_10m": 225.0,
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_payload)
        res = await provider.evaluate(lat=37.7749, lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.category == "WEATHER"
    assert res.precipitation_mm == 2.5
    assert res.wind_speed_kmh == 18.2
    assert res.wind_direction_deg == 225.0

    # Observation timestamp must match Open-Meteo 'time' with UTC timezone
    assert res.sampled_at.year == 2026
    assert res.sampled_at.month == 9
    assert res.sampled_at.day == 11
    assert res.sampled_at.hour == 12
    assert res.sampled_at.minute == 0
    assert res.sampled_at.tzinfo == timezone.utc

    # Description must contain condition, temp, precip, and wind
    assert "Slight rain" in res.description
    assert "16.5°C" in res.description
    assert "Precip: 2.5mm" in res.description
    assert "Wind: 18.2km/h" in res.description

    # to_data_source_dict exports the new fields
    ds_dict = res.to_data_source_dict()
    assert ds_dict["precipitation_mm"] == 2.5
    assert ds_dict["wind_speed_kmh"] == 18.2
    assert ds_dict["wind_direction_deg"] == 225.0
    assert ds_dict["provenance"] == "REAL"


@pytest.mark.asyncio
async def test_legacy_current_weather_fallback_parsing():
    """2. Verify backwards-compatibility with legacy 'current_weather' payload from Open-Meteo or mock responses."""
    provider = WeatherProvider()
    mock_payload = {
        "current_weather": {
            "time": "2026-09-11T10:30",
            "temperature": 19.0,
            "weathercode": 0,
            "windspeed": 8.5,
            "winddirection": 180.0,
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_payload)
        res = await provider.evaluate(lat=37.7749, lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    # Precipitation not present in legacy payload must be None (never invented)
    assert res.precipitation_mm is None
    assert res.wind_speed_kmh == 8.5
    assert res.wind_direction_deg == 180.0
    assert res.sampled_at.hour == 10
    assert res.sampled_at.minute == 30


@pytest.mark.asyncio
async def test_missing_precipitation_and_wind_not_invented():
    """3. Verify that when precipitation or wind are omitted from API feed, values remain None and are not invented."""
    provider = WeatherProvider()
    mock_payload = {
        "current": {
            "time": "2026-09-11T11:00",
            "temperature_2m": 22.0,
            "weather_code": 1,
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_payload)
        res = await provider.evaluate(lat=37.7749, lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.precipitation_mm is None
    assert res.wind_speed_kmh is None
    assert res.wind_direction_deg is None
    assert res.impact_minutes == 0


@pytest.mark.asyncio
async def test_observation_timestamp_preserves_actual_time():
    """4. Verify that observation timestamp is strictly parsed from Open-Meteo 'time', not replaced by system current time."""
    provider = WeatherProvider()
    mock_payload = {
        "current": {
            "time": "2026-01-15T08:15",
            "temperature_2m": 5.0,
            "weather_code": 3,
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_payload)
        res = await provider.evaluate(lat=37.7749, lon=-122.4194)

    # Must be 2026-01-15 08:15 UTC, regardless of current local or execution time
    assert res.sampled_at == datetime(2026, 1, 15, 8, 15, tzinfo=timezone.utc)
    assert res.sampled_at.year == 2026
    assert res.sampled_at.month == 1
    assert res.sampled_at.day == 15


@pytest.mark.asyncio
async def test_open_meteo_failure_fallback_keeps_truthful_provenance():
    """5. Verify that on network failure/timeout, provider falls back gracefully with provenance=DERIVED and no fake values."""
    provider = WeatherProvider()
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timed out")):
        res = await provider.evaluate(lat=37.7749, lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "DERIVED"
    assert res.provenance != "REAL"
    assert res.precipitation_mm is None
    assert res.wind_speed_kmh is None
    assert res.wind_direction_deg is None


@pytest.mark.asyncio
async def test_weather_data_propagates_to_eta_service():
    """6. Verify that real weather precipitation, wind, and timestamp propagate into ETAService calculate_job_eta."""
    mock_payload = {
        "current": {
            "time": "2026-09-11T13:00",
            "temperature_2m": 15.0,
            "precipitation": 1.2,
            "weather_code": 45,  # Fog (8 min base)
            "wind_speed_10m": 14.5,
            "wind_direction_10m": 270.0,
        }
    }

    eta_svc = ETAService()
    async with AsyncSessionLocal() as session:
        job = (await session.execute(select(Job).where(Job.job_number == "JOB-10002"))).scalar_one_or_none()
        if not job:
            job = (await session.execute(select(Job).where(Job.latitude.isnot(None)))).scalars().first()

        created_tech = False
        tech = (await session.execute(select(Technician).where(Technician.current_latitude.isnot(None)))).scalars().first()
        if not tech:
            from app.models.user import User
            user = (await session.execute(select(User).where(User.email == "technician@fieldops.ai"))).scalar_one_or_none()
            tech = Technician(
                id=uuid.uuid4(),
                user_id=user.id if user else uuid.uuid4(),
                employee_code="TEST-WEATHER-TECH",
                current_latitude=37.7749,
                current_longitude=-122.4194,
            )
            session.add(tech)
            await session.commit()
            created_tech = True

        assert tech is not None and job is not None

        try:
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = Response(200, json=mock_payload)
                eta_resp = await eta_svc.calculate_job_eta(job_id=job.id, technician_id=tech.id)

            weather_ds = next((ds for ds in eta_resp.data_sources if "Weather" in ds.name), None)
            assert weather_ds is not None
            assert weather_ds.provenance == "REAL"
            assert weather_ds.status == "AVAILABLE"
            assert weather_ds.precipitation_mm == 1.2
            assert weather_ds.wind_speed_kmh == 14.5
            assert weather_ds.wind_direction_deg == 270.0
            assert "2026-09-11T13:00" in weather_ds.sampled_at
            assert "Precip: 1.2mm" in weather_ds.description
            assert "Wind: 14.5km/h" in weather_ds.description
        finally:
            if created_tech:
                await session.delete(tech)
                await session.commit()


@pytest.mark.asyncio
async def test_endpoint_live_weather_returns_full_canonical_fields():
    """7. Verify that endpoint GET /api/v1/eta/weather returns full canonical fields: apparent temp, humidity, wind direction, precip prob."""
    mock_payload = {
        "current": {
            "time": "2026-09-14T11:00",
            "temperature_2m": 21.4,
            "apparent_temperature": 20.8,
            "relative_humidity_2m": 68.0,
            "precipitation": 0.0,
            "weather_code": 0,
            "wind_speed_10m": 12.0,
            "wind_direction_10m": 225.0,
        },
        "hourly": {
            "precipitation_probability": [5.0, 10.0, 15.0]
        }
    }

    provider = WeatherProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_payload)
        res = await provider.evaluate(lat=37.7749, lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.temperature_c == 21.4
    assert res.apparent_temperature_c == 20.8
    assert res.humidity_percent == 68.0
    assert res.precipitation_probability_percent == 5.0
    assert res.wind_speed_kmh == 12.0
    assert res.wind_direction_deg == 225.0
