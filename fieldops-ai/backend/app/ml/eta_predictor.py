"""
Inference Predictor Wrapper for the Trained Context-Aware Travel-Time Model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import numpy as np
import joblib

MODEL_PATH = Path(__file__).resolve().parent / "context_eta_model.joblib"


class ContextETAPredictor:
    """Loads the trained context-aware regression model and generates travel-time predictions."""

    def __init__(self, model_path: Path | None = None):
        self.model_path = model_path or MODEL_PATH
        self._model = None

    def _ensure_loaded(self):
        if self._model is None:
            if not self.model_path.exists():
                raise FileNotFoundError(
                    f"Trained model artifact not found at {self.model_path}. "
                    "Run 'python -m app.ml.train_eta_model' to generate it."
                )
            self._model = joblib.load(self.model_path)

    def predict(
        self,
        distance_km: float,
        free_flow_travel_minutes: float,
        traffic_delay_min: float = 0.0,
        precipitation_mm: float = 0.0,
        wind_speed_kmh: float = 0.0,
        weather_impact_min: float = 0.0,
        event_attendance: float = 0.0,
        event_impact_min: float = 0.0,
        road_closure_active: bool = False,
        road_impact_min: float = 0.0,
    ) -> float:
        """Generates contextual travel-time prediction in minutes."""
        self._ensure_loaded()
        features = np.array(
            [[
                float(distance_km),
                float(free_flow_travel_minutes),
                float(traffic_delay_min),
                float(precipitation_mm),
                float(wind_speed_kmh),
                float(weather_impact_min),
                float(event_attendance),
                float(event_impact_min),
                1.0 if road_closure_active else 0.0,
                float(road_impact_min),
            ]],
            dtype=np.float64,
        )
        pred = self._model.predict(features)[0]
        return round(float(pred), 1)


# Global singleton predictor instance
eta_predictor = ContextETAPredictor()
