from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict


@dataclass
class Observation:
    timestamp: str
    room_id: str
    temperature_c: float
    humidity_pct: float
    co2_ppm: float
    window_open: int
    temp_out: float
    humidity_out: float
    wind_speed: float
    is_raining: int
    hour_of_day: int

    @classmethod
    def from_sources(
        cls,
        room_id: str,
        temperature_c: float,
        humidity_pct: float,
        co2_ppm: float,
        window_open: bool,
        temp_out: float,
        humidity_out: float,
        wind_speed: float,
        is_raining: bool,
    ) -> "Observation":
        now = datetime.now(timezone.utc)
        return cls(
            timestamp=now.isoformat(),
            room_id=room_id,
            temperature_c=float(temperature_c),
            humidity_pct=float(humidity_pct),
            co2_ppm=float(co2_ppm),
            window_open=int(window_open),
            temp_out=float(temp_out),
            humidity_out=float(humidity_out),
            wind_speed=float(wind_speed),
            is_raining=int(is_raining),
            hour_of_day=int(now.hour),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_model_features(self, window_open_override: int | None = None) -> Dict[str, float]:
        return {
            "temp_in": self.temperature_c,
            "humidity_in": self.humidity_pct,
            "co2": self.co2_ppm,
            "window_open": float(self.window_open if window_open_override is None else window_open_override),
            "temp_out": self.temp_out,
            "humidity_out": self.humidity_out,
            "wind_speed": self.wind_speed,
            "is_raining": float(self.is_raining),
            "hour_of_day": float(self.hour_of_day),
        }
