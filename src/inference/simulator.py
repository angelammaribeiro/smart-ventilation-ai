from __future__ import annotations

from dataclasses import dataclass

from contracts.observation import Observation
from inference.predictor import Predictor, PredictionResult


@dataclass
class ScenarioResult:
    pred_co2_closed: float
    pred_temp_closed: float
    pred_co2_open: float
    pred_temp_open: float


class ScenarioSimulator:
    def __init__(self, predictor: Predictor) -> None:
        self.predictor = predictor

    def evaluate(self, observation: Observation) -> ScenarioResult:
        closed_features = observation.to_model_features(window_open_override=0)
        open_features = observation.to_model_features(window_open_override=1)

        pred_closed: PredictionResult = self.predictor.predict_next_10min(closed_features)
        pred_open: PredictionResult = self.predictor.predict_next_10min(open_features)

        return ScenarioResult(
            pred_co2_closed=pred_closed.co2_t_plus_10,
            pred_temp_closed=pred_closed.temp_t_plus_10,
            pred_co2_open=pred_open.co2_t_plus_10,
            pred_temp_open=pred_open.temp_t_plus_10,
        )
