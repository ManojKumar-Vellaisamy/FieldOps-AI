# Module 11 — Real Traffic Data Integration

## Overview

Module 11 upgrades the **Traffic Data Provider** inside the FieldOps AI Context-Aware ETA Engine from a placeholder state (`UNAVAILABLE`) to a production-grade, provider-based traffic data integration.

The ETA calculation engine aggregates baseline transit distance, technician GPS fixes, weather conditions, live road traffic telemetry, event access restrictions, and dispatcher manual overrides into a fully explainable, deterministic dispatch ETA.

---

## Architecture & Data Flow

```
+----------------------------+
|  Technician GPS Telemetry  | (origin_lat, origin_lon)
+----------------------------+
              |
              v
+----------------------------+
|    Job Service Address     | (dest_lat, dest_lon)
+----------------------------+
              |
              v
+-----------------------------------------------------------------------------------+
|                            TrafficDataProvider.evaluate()                        |
|                                                                                   |
|  - Validates WGS84 coordinates & checks configuration                             |
|  - Adapter Selection:                                                             |
|      * OSRM (Open Source Routing Machine) [Default zero-key open provider]        |
|      * TomTom Traffic API                 [TRAFFIC_PROVIDER=tomtom]               |
|      * OpenRouteService                   [TRAFFIC_PROVIDER=openrouteservice]     |
|  - Executes async HTTP GET with strict timeout (TRAFFIC_TIMEOUT_SECONDS = 4.0s)   |
|  - Calculates driving travel duration vs baseline speed                           |
|  - Categorizes traffic condition (Free Flow, Light, Moderate, Heavy Congestion)  |
+-----------------------------------------------------------------------------------+
              |
              v
+-----------------------------------------------------------------------------------+
|                        ContextProviderResult (TRAFFIC)                            |
|                                                                                   |
|  - source_name     : "Traffic Data"                                               |
|  - status          : AVAILABLE | UNAVAILABLE | INVALID | STALE                    |
|  - impact_minutes  : ETA adjustment (0 min if UNAVAILABLE / free-flow)             |
|  - description     : Operational explanation (driving time, condition, provider)  |
|  - sampled_at      : UTC ISO-8601 timestamp                                       |
+-----------------------------------------------------------------------------------+
              |
              v
+-----------------------------------------------------------------------------------+
|                            ContextAggregationService                              |
|                                                                                   |
|  Baseline ETA + Sum(AVAILABLE context adjustments) = Context-Aware ETA             |
+-----------------------------------------------------------------------------------+
```

---

## Traffic Data Sources & Adapters

1. **OSRM (Open Source Routing Machine)** — *Default Open Provider*
   - URL: `http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}`
   - Evaluates real driving route travel times and road network distances from OpenStreetMap graphs.
   - Calculates traffic delay: `max(0, driving_duration_min - baseline_eta_minutes)`.

2. **TomTom Traffic & Routing API**
   - URL: `https://api.tomtom.com/routing/1/calculateRoute/...`
   - Requires `TRAFFIC_PROVIDER=tomtom` and `TRAFFIC_API_KEY` in environment.
   - Computes live delay by comparing `travelTimeInSeconds` vs `noTrafficTravelTimeInSeconds`.

3. **OpenRouteService Directions API**
   - URL: `https://api.openrouteservice.org/v2/directions/driving-car`
   - Requires `TRAFFIC_PROVIDER=openrouteservice` and `TRAFFIC_API_KEY` in environment.

---

## ETA Calculation Impact

Traffic adjustments are strictly applied **only when status is `AVAILABLE`**.

$$\text{Context-Aware ETA} = \text{Baseline ETA} + \sum \text{Impact}_{\text{AVAILABLE}}$$

| Traffic Ratio ($\frac{\text{Driving Duration}}{\text{Baseline ETA}}$) | Condition Class | Impact applied |
| :--- | :--- | :--- |
| $\le 1.05$ | Free Flow | 0 min |
| $1.05 < \text{Ratio} \le 1.25$ | Light Congestion | $+\Delta$ min |
| $1.25 < \text{Ratio} \le 1.50$ | Moderate Congestion | $+\Delta$ min |
| $> 1.50$ | Heavy Congestion | $+\Delta$ min |

---

## Failure & Fallback Behaviour

The Traffic Data Provider enforces zero-exception safety:

| Failure Scenario | Provider Status | Impact Minutes | Handling |
| :--- | :--- | :--- | :--- |
| **API Online & Valid** | `AVAILABLE` | Calculated delay | Impact added to Context ETA |
| **Provider Disabled** | `UNAVAILABLE` | `0 min` | Clear rationale in description |
| **API Key Missing** | `UNAVAILABLE` | `0 min` | Safe fallback; prompts configuration |
| **Missing GPS Coords**| `UNAVAILABLE` | `0 min` | ETA engine falls back to baseline |
| **HTTP Timeout (>4.0s)**| `UNAVAILABLE` | `0 min` | Baseline ETA preserved without crash |
| **HTTP 5xx / Network Down**| `UNAVAILABLE` | `0 min` | Baseline ETA preserved without crash |
| **Invalid Coords / Malformed JSON**| `INVALID` | `0 min` | Reject invalid telemetry safely |

---

## Environment Configuration

Configuration parameters in `backend/.env` or `backend/app/core/config.py`:

```env
# Traffic Provider Configuration
TRAFFIC_PROVIDER=osrm           # Options: osrm, tomtom, openrouteservice, none
TRAFFIC_API_KEY=               # Optional API key for TomTom or OpenRouteService
TRAFFIC_API_URL=               # Optional custom API endpoint base URL
TRAFFIC_TIMEOUT_SECONDS=4.0    # Strict network timeout in seconds
```

---

## Verification & Testing

Dedicated test suite in `backend/tests/test_traffic_provider.py` covers all 10 scenario requirements:

```bash
# Run focused traffic integration tests
.venv/Scripts/pytest tests/test_traffic_provider.py -v

# Run full backend test suite
.venv/Scripts/pytest tests/ -v
```

---

## Known Limitations

1. **OSRM Public Server Rate Limits**: The public demo OSRM server (`router.project-osrm.org`) is suitable for development and demonstration. For high-volume production deployments, configure a dedicated self-hosted OSRM container via `TRAFFIC_API_URL`.
2. **Commercial Key Requirement**: Live TomTom or OpenRouteService telemetry requires valid `TRAFFIC_API_KEY` credentials in environment configuration.
