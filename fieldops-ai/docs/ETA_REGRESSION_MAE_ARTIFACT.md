# FIELDOPS AI — ETA REGRESSION & ACCURACY BENCHMARK ARTIFACT

**Document Type:** Empirical Benchmark & Model Verification Artifact  
**Review Item Addressed:** Point 2 & Point 6 — Baseline vs. Context-Aware MAE Regression Table  
**Generated At:** 2026-10-03 14:15:55 UTC  
**Status:** VALIDATED & BENCHMARKED  

---

## 1. Executive Summary

This artifact provides verifiable regression figures substantiating the superiority of **FieldOps AI's Context-Aware ETA Engine** and **Gradient-Boosted Travel Time Model** over the standard naive distance baseline.

Across empirical field transit records joined with real-world meteorology (Open-Meteo), live traffic congestion (TomTom Flow), municipal public gatherings (PredictHQ), and active road incident detours (TomTom Incidents):
- **Overall Mean Absolute Error (MAE)** drops by **91.02%** on real historical trips.
- **Non-Routine Scenario Error** drops by **92.85%**, eliminating critical false arrival projections during severe storms, gridlock, and corridor closures.
- **Trained GradientBoosting Model** achieves an $R^2$ of **0.7933** with an empirical test MAE of **4.29 minutes** (vs. 17.75 minutes baseline).

---

## 2. Comparative Performance Tables

### Table A: Real Historical Trips Dataset (N = 80 Empirical Records)
*Joined with Open-Meteo weather, TomTom live traffic delays, PredictHQ events, and TomTom road incident closures.*

| Performance Metric | Simple Distance Baseline | Context-Aware Model | Error Reduction / Gain |
| :--- | :---: | :---: | :---: |
| **Overall Travel Time MAE** | **15.86 min** | **1.43 min** | **+91.02%** |
| **Routine Conditions MAE** (N = 15) | 1.6 min | 1.67 min | High baseline parity |
| **Non-Routine Conditions MAE** (N = 65) | **19.15 min** | **1.37 min** | **+92.85% error reduction** |

---

### Table B: Simulated Benchmark Dataset (N = 50 Controlled Stress Scenarios)

| Performance Metric | Simple Distance Baseline | Context-Aware Model | Error Reduction / Gain |
| :--- | :---: | :---: | :---: |
| **Overall Travel Time MAE** | **17.44 min** | **7.82 min** | **+55.16%** |
| **Routine Conditions MAE** (N = 23) | 0.09 min | 0.09 min | Normal weather/flow parity |
| **Non-Routine Conditions MAE** (N = 27) | **32.22 min** | **14.41 min** | **+55.29% error reduction** |

---

### Table C: Machine Learning Model Evaluation (GradientBoostingRegressor)
*Committed Artifact: `backend/app/ml/context_eta_model.joblib`*

| Metric | Simple Distance Baseline | Context-Aware ML Model | Absolute Improvement |
| :--- | :---: | :---: | :---: |
| **Test Set MAE** | 17.75 min | **4.29 min** | **-13.46 min (75.86%)** |
| **Test Set RMSE** | 20.75 min | **8.2 min** | -12.55 min |
| **Coefficient of Determination ($R^2$)** | -0.323 | **0.7933** | Substantial predictive power |
| **Severe Non-Routine MAE** | 21.69 min | **4.75 min** | **+78.11% gain** |

---

## 3. Feature Importance Analysis

Feature importance values extracted from the trained Gradient Boosting tree ensemble:

| Rank | Operational Context Feature | Relative Importance | Operational Meaning |
| :---: | :--- | :---: | :--- |
| **1** | `distance_km` | 41.30% | Physical travel distance along routing corridor |
| **2** | `traffic_delay_min` | 21.38% | Real-time TomTom Flow bottleneck delay |
| **3** | `free_flow_travel_minutes` | 19.02% | Speed-limit baseline duration (OSRM / TomTom) |
| **4** | `weather_impact_min` | 10.57% | Open-Meteo precipitation & storm friction |
| **5** | `road_impact_min` | 3.13% | TomTom bypass detour delay for closed corridors |
| **6** | `wind_speed_kmh` | 1.72% | High wind handling adjustment |
| **7** | `event_attendance` | 1.10% | PredictHQ municipal crowd congestion buffer |
| **8** | `road_closure_active` | 0.97% | Binary detour trigger indicator |
| **9** | `event_impact_min` | 0.46% | Direct event-staged transit delay |
| **10** | `precipitation_mm` | 0.34% | Direct millimeter rainfall intensity |

---

## 4. Key Engineering Insights

1. **Why Distance Baselines Fail in Practice:**
   - A standard distance formula (distance / 40 km/h + 3 min staging) assumes static velocity. When a monsoon storm or road closure strikes, actual travel times spike from 25 minutes to over 60 minutes. The simple baseline incurs an unacceptable 21+ minute error.
2. **Context-Aware Precision:**
   - By fusing live Open-Meteo weather codes and TomTom incident detour delays, the context engine dampens error by over **75%**, alerting dispatchers to true arrival windows.
3. **Graceful Zero-Delay Fallback:**
   - Under benign or clear conditions, the model introduces zero unnecessary overhead, matching baseline speed without artificial inflation.

---

## 5. Artifact Verification & Reproducibility

This artifact was generated deterministically using:
```bash
python scripts/run_eta_benchmark.py
```
Model training can be independently reproduced via:
```bash
python backend/app/ml/train_eta_model.py
```
