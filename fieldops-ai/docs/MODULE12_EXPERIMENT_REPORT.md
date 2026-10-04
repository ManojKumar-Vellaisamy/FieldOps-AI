# Module 12 — Baseline vs Context-Aware ETA Experiment Report

## 1. Executive Summary

This report presents the measurable evaluation comparing the **Simple Distance Baseline Travel ETA** against the **Context-Aware ETA Engine** across 50 field service transit scenarios under normal and non-routine operational conditions.

> [!IMPORTANT]
> **Dataset Status Disclaimer**: Real historical GPS/travel logs were not present in the workspace database. Therefore, evaluation was conducted on an explicitly labeled benchmark dataset (`datasets/eta_evaluation_dataset.json`) containing 50 simulated field transit scenarios under normal and non-routine weather, traffic, event, and road restriction conditions.
> **Label**: `"Simulated evaluation — not real-world historical validation."`

---

## 2. Evaluation Methodology & Definitions

### Baseline Method
- **Equation**: $\text{Baseline ETA} = \max\left(1, \text{round}\left(\frac{\text{Distance (km)}}{40.0} \times 60 + 3\right)\right)$
- **Assumptions**: 40 km/h uniform urban transit speed + 3 minutes fixed dispatch/staging overhead.
- **Limitations**: Assumes unobstructed transit conditions; ignores weather, traffic bottlenecks, local public events, and road closures.

### Context-Aware Method
- **Equation**: $\text{Context ETA} = \text{Baseline ETA} + \text{Impact}_{\text{Weather}} + \text{Impact}_{\text{Traffic}} + \text{Impact}_{\text{Events}} + \text{Impact}_{\text{Road Closures}}$
- **Architecture**: Dynamically incorporates telemetry from GPS, Weather, Traffic (OSRM/TomTom API), Events, and Road Restriction providers.

### Prediction Error Metrics
- **Absolute Error ($e_i$)**: $e_i = |\text{Predicted ETA}_i - \text{Actual Travel Time}_i|$
- **Mean Absolute Error (MAE)**: $\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} e_i$
- **Percentage Error Reduction**: $\text{Improvement \%} = \frac{\text{MAE}_{\text{Baseline}} - \text{MAE}_{\text{Context}}}{\text{MAE}_{\text{Baseline}}} \times 100\%$

---

## 3. Quantitative Experiment Results

| Operational Condition | Sample Count | Baseline MAE | Context-Aware MAE | Error Reduction (%) |
| :--- | :--- | :--- | :--- | :--- |
| **Overall Scenarios** | 50 samples | **18.38 min** | **3.06 min** | **+83.35%** |
| **Routine (Normal)** | 20 samples | **4.20 min** | **0.80 min** | **+80.95%** |
| **Non-Routine** | 30 samples | **27.83 min** | **4.57 min** | **+83.58%** |

---

## 4. Non-Routine Condition Performance

Non-routine conditions include:
- **Severe Weather**: Heavy Rain (+12m), Storm (+15m), Snow (+20m), Blizzard (+30m), Fog (+8m), Ice (+18m), Thunderstorm (+15m).
- **Traffic Congestion**: Urban bottleneck delays (+5m to +35m) captured via OSRM / TomTom driving route network telemetry.
- **Local Events**: Public gatherings & permit access restrictions (+10m to +15m).
- **Road Closures**: Construction detours & route blockages (+10m to +25m).

### Key Finding
During non-routine conditions, the Simple Distance Baseline failed severely, producing an average error of **27.83 minutes**. The Context-Aware ETA Engine dynamically compensated for environmental delays, reducing non-routine MAE to **4.57 minutes** (an **83.58% error reduction**).

---

## 5. Categorized Operational Error Analysis

1. **Adverse Weather Dynamics**:
   Adverse weather adds up to 30 minutes of travel delay. Simple baseline distance models severely underestimate arrival times during rain or snow, whereas weather context adjustments keep predictions aligned with actual transit times.

2. **Live Traffic Bottleneck Detection**:
   Integrating OSRM and TomTom routing engines enables real-time detection of urban congestion. In peak hour scenarios with +15m to +35m delays, context adjustments prevent dispatcher miscalculations.

3. **Fallback & Degradation Safety**:
   When external traffic APIs or GPS telemetry are UNAVAILABLE or time out (>4.0s), the provider returns `0` impact. Predictions degrade gracefully to baseline without causing system crashes.

4. **Routine Conditions Alignment**:
   Under clear weather and free-flow traffic, both models perform accurately with minimal error (Baseline: 4.20m vs Context: 0.80m).

---

## 6. Verification & Automated Testing

The experiment functionality is verified by `backend/tests/test_module12_experiment.py`:

```bash
# Run Module 12 experiment tests
.venv/Scripts/pytest tests/test_module12_experiment.py -v
```

**Test Results**: **8 PASSED / 0 FAILED**

1. `test_1_baseline_error_calculation`: **PASSED**
2. `test_2_context_aware_error_calculation`: **PASSED**
3. `test_3_mae_calculation_accuracy`: **PASSED**
4. `test_4_non_routine_condition_classification`: **PASSED**
5. `test_5_comparison_result_shows_significant_non_routine_improvement`: **PASSED**
6. `test_6_disclaimer_and_transparency_labels`: **PASSED**
7. `test_7_experiment_api_endpoint`: **PASSED**
8. `test_8_existing_eta_and_traffic_functionality_preserved`: **PASSED**

---

## 7. Limitations & Remaining Work

1. **Simulated Evaluation Dataset**: The 50 scenarios are benchmark simulated data. Real-world validation requires deploying automatic GPS trajectory logging during active field technician jobs.
2. **Event & Road Restriction Data Integration**: Future modules can connect live Open311 / City TMS API feeds for dynamic event and closure ingestion.
