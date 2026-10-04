"""
Reproducible Machine Learning Training Pipeline for Context-Aware Travel-Time (ETA) Prediction.

Substantiates Point 4 of College Technical Review:
- Trains an empirical gradient-boosted regression model on real historical trip records joined with
  Open-Meteo weather, TomTom live traffic delays, PredictHQ events, and road closures.
- Evaluates Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), and R² score against the
  simple distance-based baseline.
- Persists committed model artifact (context_eta_model.joblib) and metrics (model_metrics.json).
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np

# Ensure sklearn and joblib are available
try:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    import joblib
except ImportError as exc:
    raise ImportError(
        "Required ML libraries (scikit-learn, joblib, numpy) must be installed. "
        "Run: pip install scikit-learn joblib numpy"
    ) from exc

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATASET_PATH = BASE_DIR / "datasets" / "real_historical_trips_dataset.json"
if not DATASET_PATH.exists():
    DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "datasets" / "real_historical_trips_dataset.json"
MODEL_DIR = Path(__file__).resolve().parent
ARTIFACT_PATH = MODEL_DIR / "context_eta_model.joblib"
METRICS_PATH = MODEL_DIR / "model_metrics.json"

FEATURE_NAMES = [
    "distance_km",
    "free_flow_travel_minutes",
    "traffic_delay_min",
    "precipitation_mm",
    "wind_speed_kmh",
    "weather_impact_min",
    "event_attendance",
    "event_impact_min",
    "road_closure_active",
    "road_impact_min",
]


def load_dataset() -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Loads and formats feature matrix and target travel time vectors."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Historical dataset not found at {DATASET_PATH}")

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = data.get("samples", [])
    if len(samples) < 10:
        raise ValueError(f"Insufficient samples ({len(samples)}) for ML training; minimum 10 required.")

    X = []
    y = []

    for s in samples:
        row = [
            float(s.get("distance_km", 0.0)),
            float(s.get("free_flow_travel_minutes", 0.0)),
            float(s.get("traffic_delay_min", 0.0)),
            float(s.get("precipitation_mm", 0.0)),
            float(s.get("wind_speed_kmh", 0.0)),
            float(s.get("weather_impact_min", 0.0)),
            float(s.get("event_attendance", 0.0)),
            float(s.get("event_impact_min", 0.0)),
            1.0 if s.get("road_closure_active") else 0.0,
            float(s.get("road_impact_min", 0.0)),
        ]
        X.append(row)
        y.append(float(s["actual_travel_minutes"]))

    return np.array(X, dtype=np.float64), np.array(y, dtype=np.float64), samples


def compute_baseline_predictions(X: np.ndarray) -> np.ndarray:
    """Simple Distance Baseline: (distance_km / 40.0) * 60.0 + 3.0 min staging."""
    dist_km = X[:, 0]
    return np.maximum(1.0, np.round((dist_km / 40.0) * 60.0 + 3.0))


def train_and_evaluate():
    """Executes the end-to-end model training, evaluation, and artifact serialization."""
    print("=" * 75)
    print("FIELDOPS AI — CONTEXT-AWARE TRAVEL TIME ML MODEL TRAINING PIPELINE")
    print("=" * 75)

    X, y, raw_samples = load_dataset()
    n_samples = len(y)
    print(f"[Dataset] Loaded {n_samples} empirical trip records from {DATASET_PATH.name}")

    # Split into Train / Test (80 / 20) with fixed seed for strict reproducibility
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, range(n_samples), test_size=0.20, random_state=42
    )

    print(f"[Split] Train samples: {len(y_train)}, Test evaluation samples: {len(y_test)}")

    # 1. Baseline Evaluation on Test Set
    baseline_preds = compute_baseline_predictions(X_test)
    baseline_mae = float(mean_absolute_error(y_test, baseline_preds))
    baseline_rmse = float(np.sqrt(mean_squared_error(y_test, baseline_preds)))
    baseline_r2 = float(r2_score(y_test, baseline_preds))

    # 2. Train Context-Aware ML Model (GradientBoostingRegressor)
    model = GradientBoostingRegressor(
        n_estimators=120,
        learning_rate=0.08,
        max_depth=4,
        subsample=0.85,
        random_state=42,
    )
    model.fit(X_train, y_train)

    # 3. Model Predictions on Test Set
    model_preds = model.predict(X_test)
    model_mae = float(mean_absolute_error(y_test, model_preds))
    model_rmse = float(np.sqrt(mean_squared_error(y_test, model_preds)))
    model_r2 = float(r2_score(y_test, model_preds))

    # 4. Routine vs Non-Routine Stratified Evaluation
    test_samples = [raw_samples[i] for i in idx_test]
    routine_indices = [i for i, s in enumerate(test_samples) if not s.get("is_non_routine", False)]
    non_routine_indices = [i for i, s in enumerate(test_samples) if s.get("is_non_routine", False)]

    # Routine MAEs
    if routine_indices:
        b_routine_mae = float(mean_absolute_error(y_test[routine_indices], baseline_preds[routine_indices]))
        m_routine_mae = float(mean_absolute_error(y_test[routine_indices], model_preds[routine_indices]))
    else:
        b_routine_mae = baseline_mae
        m_routine_mae = model_mae

    # Non-Routine MAEs
    if non_routine_indices:
        b_non_routine_mae = float(mean_absolute_error(y_test[non_routine_indices], baseline_preds[non_routine_indices]))
        m_non_routine_mae = float(mean_absolute_error(y_test[non_routine_indices], model_preds[non_routine_indices]))
    else:
        b_non_routine_mae = baseline_mae
        m_non_routine_mae = model_mae

    improvement_pct = round(((baseline_mae - model_mae) / baseline_mae) * 100.0, 2)
    non_routine_improvement_pct = round(
        ((b_non_routine_mae - m_non_routine_mae) / b_non_routine_mae) * 100.0, 2
    )

    # 5. Feature Importances
    importances = model.feature_importances_
    feature_ranking = [
        {"feature": name, "importance": round(float(imp), 4)}
        for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True)
    ]

    print("\n" + "-" * 75)
    print("COMPARATIVE EVALUATION SUMMARY (Baseline vs Context-Aware ML Model)")
    print("-" * 75)
    print(f"Simple Baseline MAE:       {baseline_mae:.2f} min (RMSE: {baseline_rmse:.2f} min, R²: {baseline_r2:.3f})")
    print(f"Context-Aware ML MAE:      {model_mae:.2f} min (RMSE: {model_rmse:.2f} min, R²: {model_r2:.3f})")
    print(f"Overall MAE Reduction:     {improvement_pct:.2f}% improvement")
    print("-" * 75)
    print(f"Routine Conditions MAE:    Baseline: {b_routine_mae:.2f}m | ML Model: {m_routine_mae:.2f}m")
    print(f"Non-Routine Conditions MAE: Baseline: {b_non_routine_mae:.2f}m | ML Model: {m_non_routine_mae:.2f}m")
    print(f"Non-Routine Error Gain:    {non_routine_improvement_pct:.2f}% error reduction in severe conditions!")
    print("-" * 75)

    print("\n[Feature Importance Ranking]")
    for rank, f in enumerate(feature_ranking, 1):
        print(f"  {rank}. {f['feature']:<28} {f['importance'] * 100:.2f}%")

    # 6. Save Committed Model Artifact
    joblib.dump(model, ARTIFACT_PATH)
    print(f"\n[Artifact Saved] Trained ML model committed to: {ARTIFACT_PATH}")

    # 7. Save Metrics JSON
    metrics = {
        "model_type": "GradientBoostingRegressor",
        "n_estimators": 120,
        "max_depth": 4,
        "total_samples": n_samples,
        "train_samples": len(y_train),
        "test_samples": len(y_test),
        "routine_test_count": len(routine_indices),
        "non_routine_test_count": len(non_routine_indices),
        "metrics": {
            "baseline_mae": round(baseline_mae, 2),
            "baseline_rmse": round(baseline_rmse, 2),
            "baseline_r2": round(baseline_r2, 4),
            "model_mae": round(model_mae, 2),
            "model_rmse": round(model_rmse, 2),
            "model_r2": round(model_r2, 4),
            "overall_improvement_percent": improvement_pct,
            "routine_baseline_mae": round(b_routine_mae, 2),
            "routine_model_mae": round(m_routine_mae, 2),
            "non_routine_baseline_mae": round(b_non_routine_mae, 2),
            "non_routine_model_mae": round(m_non_routine_mae, 2),
            "non_routine_improvement_percent": non_routine_improvement_pct,
        },
        "feature_importances": feature_ranking,
        "artifact_file": ARTIFACT_PATH.name,
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[Metrics Saved] Model performance metrics saved to: {METRICS_PATH}")
    print("=" * 75)
    return metrics


if __name__ == "__main__":
    train_and_evaluate()
