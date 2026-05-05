from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import joblib
import numpy as np


@dataclass
class PredictionResult:
    co2_t_plus_10: float
    temp_t_plus_10: float


class Predictor:
    def __init__(self, model_path: str) -> None:
        self.model_path = Path(model_path)
        self.model = None
        self._load_model_if_possible()

    def _load_model_if_possible(self) -> None:
        if not self.model_path.exists() or self.model_path.stat().st_size == 0:
            self.model = None
            return
        try:
            self.model = joblib.load(self.model_path)
        except Exception:
            self.model = None

    def predict_next_10min(self, features: Dict[str, float]) -> PredictionResult:
        if self.model is None:
            co2_t_plus_10 = self._fallback_co2_forecast(features)
            temp_t_plus_10 = self._fallback_temp_forecast(features)
            return PredictionResult(co2_t_plus_10=co2_t_plus_10, temp_t_plus_10=temp_t_plus_10)

        ordered = np.array(
            [[
                features["temp_in"],
                features["humidity_in"],
                features["co2"],
                features["window_open"],
                features["temp_out"],
                features["humidity_out"],
                features["wind_speed"],
                features["is_raining"],
                features["hour_of_day"],
            ]],
            dtype=float,
        )

        prediction = self.model.predict(ordered)[0]

        if isinstance(prediction, (list, tuple, np.ndarray)) and len(prediction) >= 2:
            return PredictionResult(co2_t_plus_10=float(prediction[0]), temp_t_plus_10=float(prediction[1]))

        return PredictionResult(
            co2_t_plus_10=self._fallback_co2_forecast(features),
            temp_t_plus_10=self._fallback_temp_forecast(features),
        )

    def _fallback_co2_forecast(self, features: Dict[str, float]) -> float:
        co2_now = float(features["co2"])
        window_open = int(features["window_open"])
        wind_speed = float(features["wind_speed"])

        if window_open:
            reduction = 90.0 + min(wind_speed * 8.0, 60.0)
            return max(420.0, co2_now - reduction)
        increase = 70.0
        return min(2500.0, co2_now + increase)

    def _fallback_temp_forecast(self, features: Dict[str, float]) -> float:
        temp_in = float(features["temp_in"])
        temp_out = float(features["temp_out"])
        window_open = int(features["window_open"])

        if window_open:
            adjustment = (temp_out - temp_in) * 0.25
            return temp_in + adjustment
        drift = (temp_out - temp_in) * 0.05
        return temp_in + drift
