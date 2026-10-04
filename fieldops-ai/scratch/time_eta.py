import asyncio
import time
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app.database.session import AsyncSessionLocal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.job import Job
from app.models.assignment import Assignment
from app.models.technician import Technician
from app.models.eta_override import ETAOverride
from app.services.eta_service import ETAService, _haversine_miles, _miles_to_km, _baseline_minutes
from app.services.context_providers import (
    GPSLocationProvider,
    WeatherProvider,
    TrafficDataProvider,
    EventsDataProvider,
    RoadRestrictionProvider,
)
from app.services.settings_service import SettingsService

async def main():
    async with AsyncSessionLocal() as session:
        # Find jobs that have assigned technicians with GPS
        stmt = select(Job).join(Assignment).join(Technician).where(
            Technician.current_latitude.isnot(None),
            Job.latitude.isnot(None)
        )
        res = await session.execute(stmt)
        jobs = res.scalars().all()
        print(f"Found {len(jobs)} jobs with assigned technician GPS and job coords.")
        if not jobs:
            # Let's find any job
            res2 = await session.execute(select(Job))
            all_jobs = res2.scalars().all()
            print(f"Total jobs in DB: {len(all_jobs)}")
            for j in all_jobs[:5]:
                print(f"Job: {j.id} - status: {j.status} - lat/lon: {j.latitude},{j.longitude}")
            return

        target_job = jobs[0]
        print(f"Testing with job_id: {target_job.id}, job_number: {target_job.job_number}, status: {target_job.status}")

    service = ETAService()
    
    # Step-by-step timing
    print("\n--- Step-by-step provider timing ---")
    
    # DB fetch
    t_db0 = time.perf_counter()
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Job)
            .where(Job.id == target_job.id)
            .options(
                selectinload(Job.assignments)
                .selectinload(Assignment.technician)
                .selectinload(Technician.user),
                selectinload(Job.eta_overrides).selectinload(ETAOverride.dispatcher),
            )
        )
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        target_tech = job.assignments[0].technician
    t_db = time.perf_counter() - t_db0
    print(f"1. Database query: {t_db:.3f}s")
    
    haversine_dist_miles = round(
        _haversine_miles(
            job.latitude,
            job.longitude,
            target_tech.current_latitude,
            target_tech.current_longitude,
        ),
        2,
    )
    fallback_baseline_eta = _baseline_minutes(haversine_dist_miles, speed_mph=25.0)

    # GPS
    t0 = time.perf_counter()
    gps_res = await GPSLocationProvider().evaluate(
        technician_lat=target_tech.current_latitude,
        technician_lon=target_tech.current_longitude,
    )
    t_gps = time.perf_counter() - t0
    print(f"2. GPSLocationProvider: {t_gps:.3f}s")

    # Traffic (TomTom)
    t0 = time.perf_counter()
    traffic_res = await TrafficDataProvider().evaluate(
        origin_lat=target_tech.current_latitude,
        origin_lon=target_tech.current_longitude,
        dest_lat=job.latitude,
        dest_lon=job.longitude,
        baseline_eta_minutes=fallback_baseline_eta,
    )
    t_traffic = time.perf_counter() - t0
    print(f"3. TrafficDataProvider (TomTom): {t_traffic:.3f}s (status={traffic_res.status}, prov={traffic_res.provenance})")

    baseline_eta = 9 # approximation
    dist_miles = haversine_dist_miles
    route_geometry = traffic_res.route_geometry

    # Weather (Open-Meteo)
    t0 = time.perf_counter()
    weather_res = await WeatherProvider().evaluate(
        lat=target_tech.current_latitude,
        lon=target_tech.current_longitude,
        dest_lat=job.latitude,
        dest_lon=job.longitude,
        baseline_eta_minutes=baseline_eta,
        distance_miles=dist_miles,
    )
    t_weather = time.perf_counter() - t0
    print(f"4. WeatherProvider (Open-Meteo): {t_weather:.3f}s (status={weather_res.status}, prov={weather_res.provenance})")

    # Events (PredictHQ)
    t0 = time.perf_counter()
    events_res = await EventsDataProvider().evaluate(
        origin_lat=target_tech.current_latitude,
        origin_lon=target_tech.current_longitude,
        dest_lat=job.latitude,
        dest_lon=job.longitude,
        distance_miles=dist_miles,
        baseline_eta_minutes=baseline_eta,
        route_geometry=route_geometry,
        traffic_delay_seconds=traffic_res.traffic_delay_seconds,
    )
    t_events = time.perf_counter() - t0
    print(f"5. EventsDataProvider (PredictHQ): {t_events:.3f}s (status={events_res.status}, prov={events_res.provenance})")

    # Road Restrictions (TomTom)
    t0 = time.perf_counter()
    road_res = await RoadRestrictionProvider().evaluate(
        origin_lat=target_tech.current_latitude,
        origin_lon=target_tech.current_longitude,
        dest_lat=job.latitude,
        dest_lon=job.longitude,
        distance_miles=dist_miles,
        baseline_eta_minutes=baseline_eta,
        route_geometry=route_geometry,
        original_route_time_seconds=traffic_res.live_travel_time_seconds or (baseline_eta * 60),
        traffic_delay_seconds=traffic_res.traffic_delay_seconds,
    )
    t_road = time.perf_counter() - t0
    print(f"6. RoadRestrictionProvider (TomTom): {t_road:.3f}s (status={road_res.status}, prov={road_res.provenance})")

    t_sum = t_db + t_gps + t_traffic + t_weather + t_events + t_road
    print(f"\nSum of sequential operations: {t_sum:.3f}s")


if __name__ == "__main__":
    asyncio.run(main())
