from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VentilationDecision:
    action: str
    reason: str


class DecisionEngine:
    def __init__(
        self,
        co2_drop_threshold: float = 80.0,
        comfort_temp_drop_limit: float = 1.5,
        co2_hard_limit: float = 1200.0,
    ) -> None:
        self.co2_drop_threshold = co2_drop_threshold
        self.comfort_temp_drop_limit = comfort_temp_drop_limit
        self.co2_hard_limit = co2_hard_limit

    def decide(
        self,
        co2_now: float,
        window_open_now: bool,
        pred_co2_closed: float,
        pred_temp_closed: float,
        pred_co2_open: float,
        pred_temp_open: float,
        temp_now: float,
    ) -> VentilationDecision:
        predicted_co2_drop = pred_co2_closed - pred_co2_open
        predicted_temperature_drop = temp_now - pred_temp_open

        if not window_open_now and co2_now >= self.co2_hard_limit:
            return VentilationDecision("open_window", "CO2 above hard limit")

        if (
            not window_open_now
            and predicted_co2_drop >= self.co2_drop_threshold
            and predicted_temperature_drop <= self.comfort_temp_drop_limit
        ):
            return VentilationDecision(
                "open_window",
                "Opening window reduces CO2 significantly with acceptable temperature drop",
            )

        if window_open_now and (pred_co2_open < 700.0) and (pred_temp_open < temp_now - self.comfort_temp_drop_limit):
            return VentilationDecision("close_window", "Room likely to overcool while air quality is already good")

        return VentilationDecision("hold", "No strong action required")
