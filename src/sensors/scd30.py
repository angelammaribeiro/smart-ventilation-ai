from __future__ import annotations

import random


class SCD30Sensor:
    _mock_co2_ppm: float | None = None

    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock

    def read_co2(self) -> float:
        if self.use_mock:
            if SCD30Sensor._mock_co2_ppm is None:
                SCD30Sensor._mock_co2_ppm = round(random.uniform(650.0, 1050.0), 1)
            else:
                SCD30Sensor._mock_co2_ppm += random.uniform(-55.0, 55.0)
                SCD30Sensor._mock_co2_ppm = min(1700.0, max(450.0, SCD30Sensor._mock_co2_ppm))

            return round(SCD30Sensor._mock_co2_ppm, 1)
        raise NotImplementedError("Real SCD30 integration not implemented in scaffold.")
