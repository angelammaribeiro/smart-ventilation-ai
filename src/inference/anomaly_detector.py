from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import joblib
import numpy as np


@dataclass
class AnomalyResult:
    score: float
    is_anomaly: bool


class AnomalyDetector:
    def __init__(self, model_path: str) -> None:
        self.model_path = Path(model_path)
        self.bundle = None
        self._load_model_if_possible()

    def _load_model_if_possible(self) -> None:
        if not self.model_path.exists() or self.model_path.stat().st_size == 0:
            self.bundle = None
            return
        try:
            self.bundle = joblib.load(self.model_path)
        except Exception:
            self.bundle = None

    def score_observation(self, features: Dict[str, float]) -> AnomalyResult | None:
        if not isinstance(self.bundle, dict):
            return None

        model = self.bundle.get("model")
        feature_cols = self.bundle.get("feature_cols")
        if model is None or not isinstance(feature_cols, list) or not feature_cols:
            return None

        ordered = np.array([[float(features.get(col, 0.0)) for col in feature_cols]], dtype=float)

        try:
            # IsolationForest: lower decision_function means more anomalous.
            raw_score = float(model.decision_function(ordered)[0])
            is_anomaly = bool(model.predict(ordered)[0] == -1)
        except Exception:
            return None

        return AnomalyResult(score=raw_score, is_anomaly=is_anomaly)
