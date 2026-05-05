from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass
class WeatherSnapshot:
    temp_out: float
    humidity_out: float
    wind_speed: float
    is_raining: int


class WeatherAPI:
    def __init__(self, latitude: float = 38.7223, longitude: float = -9.1393) -> None:
        self.latitude = latitude
        self.longitude = longitude

    def fetch_current(self) -> WeatherSnapshot:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={self.latitude}&longitude={self.longitude}"
            "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"
        )
        try:
            response = requests.get(url, timeout=4)
            response.raise_for_status()
            payload = response.json().get("current", {})
            precipitation = float(payload.get("precipitation", 0.0))
            return WeatherSnapshot(
                temp_out=float(payload.get("temperature_2m", 18.0)),
                humidity_out=float(payload.get("relative_humidity_2m", 60.0)),
                wind_speed=float(payload.get("wind_speed_10m", 2.5)),
                is_raining=int(precipitation > 0.0),
            )
        except Exception:
            return WeatherSnapshot(temp_out=18.0, humidity_out=60.0, wind_speed=2.5, is_raining=0)
