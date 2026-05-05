from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np


@dataclass
class PolicyTargets:
    temp_min: float = 21.0
    temp_max: float = 24.0
    humidity_min: float = 40.0
    humidity_max: float = 60.0


@dataclass
class CounterfactualDecision:
    action: str
    score_open: float
    score_close: float
    pred_temp_open: float
    pred_humidity_open: float
    pred_temp_close: float
    pred_humidity_close: float


class CounterfactualPolicy:
    def __init__(self, model_path: str) -> None:
        self.model_path = Path(model_path)
        self.bundle: dict[str, Any] | None = None
        self._load_if_possible()

    def _load_if_possible(self) -> None:
        if not self.model_path.exists() or self.model_path.stat().st_size == 0:
            self.bundle = None
            return
        try:
            loaded = joblib.load(self.model_path)
            if isinstance(loaded, dict):
                self.bundle = loaded
            else:
                self.bundle = None
        except Exception:
            self.bundle = None

    @staticmethod
    def _band_penalty(value: float, low: float, high: float) -> float:
        if value < low:
            return low - value
        if value > high:
            return value - high
        return 0.0

    def _comfort_score(self, temp_next: float, humidity_next: float, targets: PolicyTargets) -> float:
        temp_penalty = self._band_penalty(temp_next, targets.temp_min, targets.temp_max)
        humidity_penalty = self._band_penalty(humidity_next, targets.humidity_min, targets.humidity_max)
        return float(temp_penalty + (0.5 * humidity_penalty))

    def _predict_action_outcome(self, action: str, features: dict[str, float]) -> tuple[float, float]:
        if not self.bundle:
            raise RuntimeError("Model bundle not loaded")

        feature_cols = self.bundle.get("feature_cols", [])
        models = self.bundle.get("models", {})
        model = models.get(action)
        if model is None:
            raise RuntimeError(f"Missing model for action: {action}")

        ordered = np.array([[float(features[col]) for col in feature_cols]], dtype=float)
        pred = model.predict(ordered)[0]
        return float(pred[0]), float(pred[1])

    def recommend(self, features: dict[str, float], targets: PolicyTargets) -> CounterfactualDecision:
        temp_open, humidity_open = self._predict_action_outcome("open_window", features)
        temp_close, humidity_close = self._predict_action_outcome("close_window", features)

        score_open = self._comfort_score(temp_open, humidity_open, targets)
        score_close = self._comfort_score(temp_close, humidity_close, targets)

        action = "open_window" if score_open <= score_close else "close_window"

        return CounterfactualDecision(
            action=action,
            score_open=score_open,
            score_close=score_close,
            pred_temp_open=temp_open,
            pred_humidity_open=humidity_open,
            pred_temp_close=temp_close,
            pred_humidity_close=humidity_close,
        )
