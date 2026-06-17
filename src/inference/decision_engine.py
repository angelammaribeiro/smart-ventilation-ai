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
        co2_hard_limit: float = 1400.0,
        co2_bad_limit: float = 1000.0,
        co2_good_limit: float = 700.0,
        temp_hot_limit: float = 27.0,
        temp_cold_limit: float = 19.0,
        min_outdoor_cooling_delta: float = 1.0,
    ) -> None:
        self.co2_drop_threshold = co2_drop_threshold
        self.comfort_temp_drop_limit = comfort_temp_drop_limit
        self.co2_hard_limit = co2_hard_limit
        self.co2_bad_limit = co2_bad_limit
        self.co2_good_limit = co2_good_limit
        self.temp_hot_limit = temp_hot_limit
        self.temp_cold_limit = temp_cold_limit
        self.min_outdoor_cooling_delta = min_outdoor_cooling_delta

    def decide(
        self,
        co2_now: float,
        window_open_now: bool,
        pred_co2_closed: float,
        pred_temp_closed: float,
        pred_co2_open: float,
        pred_temp_open: float,
        temp_now: float,
        temp_out_now: float | None = None,
        is_raining_now: bool = False,
    ) -> VentilationDecision:
        predicted_co2_drop = pred_co2_closed - pred_co2_open
        predicted_temperature_drop = temp_now - pred_temp_open

        # 1) Air-quality anomalies (health-first)
        if not window_open_now and co2_now >= self.co2_hard_limit:
            return VentilationDecision("open_window", "CO2 in critical range")

        if not window_open_now and co2_now >= self.co2_bad_limit:
            return VentilationDecision("open_window", "CO2 above poor-air threshold")

        # 2) Thermal anomalies
        if not window_open_now and temp_now >= self.temp_hot_limit:
            if is_raining_now:
                return VentilationDecision("hold", "Indoor temperature high but raining outside")
            if temp_out_now is None or temp_out_now <= temp_now - self.min_outdoor_cooling_delta:
                return VentilationDecision("open_window", "Indoor temperature above hot threshold")

        if window_open_now and temp_now <= self.temp_cold_limit:
            return VentilationDecision("close_window", "Indoor temperature below cold threshold")

        # 3) Comfort/safety close checks
        if window_open_now and is_raining_now and co2_now <= self.co2_bad_limit:
            return VentilationDecision("close_window", "Raining and air quality is acceptable")

        if window_open_now and co2_now <= self.co2_good_limit and temp_now <= self.temp_cold_limit + 1.0:
            return VentilationDecision("close_window", "Air quality already good and room is cool")

        if (
            not window_open_now
            and predicted_co2_drop >= self.co2_drop_threshold
            and predicted_temperature_drop <= self.comfort_temp_drop_limit
        ):
            return VentilationDecision(
                "open_window",
                "Opening window reduces CO2 significantly with acceptable temperature drop",
            )

        if (
            window_open_now
            and (pred_co2_open < self.co2_good_limit)
            and (pred_temp_open < temp_now - self.comfort_temp_drop_limit)
        ):
            return VentilationDecision("close_window", "Room likely to overcool while air quality is already good")

        return VentilationDecision("hold", "No strong action required")
