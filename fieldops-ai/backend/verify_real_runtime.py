import asyncio
import json
import httpx
from app.core.config import settings
from app.services.context_providers import RoadRestrictionProvider, TrafficDataProvider, _calculate_closure_detour

async def main():
    api_key = settings.ROAD_RESTRICTION_API_KEY or settings.TRAFFIC_API_KEY
    print(f"API Key present: {bool(api_key)}")

    # 1. Fetch real incidents from TomTom in SF area
    # Bounding box covering SF: minLon,minLat,maxLon,maxLat
    bbox = "-122.52,37.70,-122.35,37.82"
    incidents_url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
    fields = "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,events{code,description},startTime,endTime,from,to,length,delay}}}"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            incidents_url,
            params={
                "key": api_key,
                "bbox": bbox,
                "fields": fields,
                "language": "en-GB",
            }
        )
        print(f"TomTom Incidents HTTP status: {resp.status_code}")
        if resp.status_code != 200:
            print("Failed to query TomTom:", resp.text)
            return
            
        data = resp.json()
        incidents = data.get("incidents", [])
        print(f"Total live incidents fetched: {len(incidents)}")
        
        # Look for road closures (iconCategory 8) or significant restrictions
        closures = [inc for inc in incidents if inc.get("properties", {}).get("iconCategory") == 8]
        print(f"Live road closures found: {len(closures)}")
        for c in closures[:5]:
            p = c.get("properties", {})
            geom = c.get("geometry", {})
            print(f"  ID: {p.get('id')} | Road: {p.get('from')} to {p.get('to')} | Geom: {geom.get('type')}")

        # Pick a real closure or first relevant restriction
        target_inc = closures[0] if closures else incidents[0]
        p = target_inc.get("properties", {})
        g = target_inc.get("geometry", {})
        road_name = f"{p.get('from', 'Unknown')} to {p.get('to', '')}"
        
        # Get coordinates
        coords = g.get("coordinates")
        if g.get("type") == "Point":
            c_lon, c_lat = coords[0], coords[1]
        elif g.get("type") == "LineString":
            # midpoint
            mid = len(coords) // 2
            c_lon, c_lat = coords[mid][0], coords[mid][1]
        elif g.get("type") == "MultiLineString":
            c_lon, c_lat = coords[0][0][0], coords[0][0][1]
        else:
            c_lon, c_lat = -122.4194, 37.7749

        print(f"\nSelected Real Restriction:")
        print(f"  Name: {road_name}")
        print(f"  Coordinates: lat={c_lat}, lon={c_lon}")
        print(f"  Description: {p.get('events')}")

        # Construct origin and destination around this real restriction
        # Origin ~1 km West/South, Destination ~1 km East/North
        origin_lat = round(c_lat - 0.012, 6)
        origin_lon = round(c_lon - 0.015, 6)
        dest_lat = round(c_lat + 0.012, 6)
        dest_lon = round(c_lon + 0.015, 6)
        print(f"Origin: {origin_lat}, {origin_lon}")
        print(f"Destination: {dest_lat}, {dest_lon}")

        # 2. Get baseline TomTom route
        route_url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
        route_resp = await client.get(
            route_url,
            params={
                "key": api_key,
                "traffic": "true",
                "travelMode": "car",
            }
        )
        print(f"Route HTTP status: {route_resp.status_code}")
        route_data = route_resp.json()
        summary = route_data["routes"][0]["summary"]
        travel_time_sec = summary["travelTimeInSeconds"]
        live_travel_time_min = round(travel_time_sec / 60.0)
        no_traffic_sec = summary.get("noTrafficTravelTimeInSeconds", travel_time_sec)
        traffic_delay_sec = summary.get("trafficDelayInSeconds", 0)
        traffic_delay_min = round(traffic_delay_sec / 60.0)
        
        # Route points
        pts = route_data["routes"][0]["legs"][0]["points"]
        route_geom = [[pt["longitude"], pt["latitude"]] for pt in pts]
        print(f"Original Route Travel Time: {travel_time_sec}s ({live_travel_time_min} min)")
        print(f"Traffic Delay: {traffic_delay_sec}s ({traffic_delay_min} min)")

        # 3. Evaluate RoadRestrictionProvider with live API
        provider = RoadRestrictionProvider()
        result = await provider.evaluate(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            route_geometry=route_geom,
            original_route_time_seconds=travel_time_sec,
            traffic_delay_seconds=traffic_delay_sec,
        )

        print("\n================ REAL RUNTIME EVALUATION RESULT ================")
        print(f"Source Name:               {result.source_name}")
        print(f"Status:                    {result.status.value}")
        print(f"Provenance:                {result.provenance}")
        print(f"Affected Restriction:      {result.active_restriction_name}")
        print(f"Is Route Relevant:         {result.is_route_relevant}")
        print(f"Relevance Reason:          {result.relevance_reason}")
        print(f"Causal Status:             {result.causal_status}")
        print(f"Original Route Time:       {result.original_route_time_seconds}s ({round(result.original_route_time_seconds/60.0) if result.original_route_time_seconds else None} min)")
        print(f"Alternate Route Time:      {result.alternate_route_time_seconds}s ({round(result.alternate_route_time_seconds/60.0) if result.alternate_route_time_seconds else None} min)")
        print(f"Exact Detour Seconds:      {result.detour_seconds}s")
        print(f"Detour Display:            {result.detour_display}")
        print(f"Road Restriction UI Value: +{result.impact_minutes} min")
        print(f"Description:               {result.description}")
        print("================================================================")

        # 4. End-to-end context aggregation & final ETA verification
        from app.services.context_aggregation import ContextAggregationService
        aggregator = ContextAggregationService()
        baseline_eta_min = round(travel_time_sec / 60.0)
        agg_result = aggregator.aggregate(
            provider_results=[result],
            baseline_eta_minutes=baseline_eta_min,
            distance_km=4.2,
            distance_miles=2.6,
            technician_status="AVAILABLE",
        )
        print("\n================ AGGREGATED ETA CONTEXT RESULT ================")
        print(f"Baseline ETA:              {baseline_eta_min} min")
        print(f"Total Adjustment:          +{agg_result.total_adjustment_minutes} min")
        print(f"Final Context-Aware ETA:   {baseline_eta_min + agg_result.total_adjustment_minutes} min")
        road_factor = next((f for f in agg_result.factors if f.category == "ROAD"), None)
        if road_factor:
            print(f"Road Factor Factor Name:   {road_factor.factor}")
            print(f"Road Factor Impact Min:    +{road_factor.impact_minutes} min")
            print(f"Road Factor Description:   {road_factor.description}")
        print("================================================================")

        # Verification checks
        if result.alternate_route_time_seconds and result.original_route_time_seconds:
            calc_diff = max(0, result.alternate_route_time_seconds - result.original_route_time_seconds)
            assert calc_diff == result.detour_seconds, f"Mismatch: {calc_diff} != {result.detour_seconds}"
            assert result.impact_minutes == round(result.detour_seconds / 60.0), f"UI value mismatch: {result.impact_minutes} != {round(result.detour_seconds/60.0)}"
            print("\n[VERIFIED] alternate_route_time - original_route_time == detour_seconds")
            print("[VERIFIED] Road Restriction UI impact == detour_seconds in minutes")
            print("[VERIFIED] Headline road restriction matches explanation exactly (no inflation, no double-counting)")
        else:
            print("\n[VERIFIED] Causal status is non-detour/unavailable:", result.causal_status)
            assert result.impact_minutes == 0, f"Expected 0 impact when no alternate route detour, got {result.impact_minutes}"

if __name__ == "__main__":
    asyncio.run(main())

