from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class DHT20Reading:
    temperature_c: float
    humidity_pct: float


class DHT20Sensor:
    _mock_temp_c: float | None = None
    _mock_humidity_pct: float | None = None

    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock

    def read(self) -> DHT20Reading:
        if self.use_mock:
            if DHT20Sensor._mock_temp_c is None:
                DHT20Sensor._mock_temp_c = round(random.uniform(22.0, 24.5), 2)
            else:
                DHT20Sensor._mock_temp_c += random.uniform(-0.25, 0.25)
                DHT20Sensor._mock_temp_c = min(27.0, max(20.0, DHT20Sensor._mock_temp_c))

            if DHT20Sensor._mock_humidity_pct is None:
                DHT20Sensor._mock_humidity_pct = round(random.uniform(48.0, 62.0), 2)
            else:
                DHT20Sensor._mock_humidity_pct += random.uniform(-1.2, 1.2)
                DHT20Sensor._mock_humidity_pct = min(75.0, max(35.0, DHT20Sensor._mock_humidity_pct))

            return DHT20Reading(
                temperature_c=round(DHT20Sensor._mock_temp_c, 2),
                humidity_pct=round(DHT20Sensor._mock_humidity_pct, 2),
            )
        raise NotImplementedError("Real DHT20 integration not implemented in scaffold.")
