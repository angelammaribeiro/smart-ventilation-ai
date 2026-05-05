from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class DHT20Reading:
    temperature_c: float
    humidity_pct: float


class DHT20Sensor:
    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock

    def read(self) -> DHT20Reading:
        if self.use_mock:
            return DHT20Reading(
                temperature_c=round(random.uniform(21.0, 26.0), 2),
                humidity_pct=round(random.uniform(45.0, 65.0), 2),
            )
        raise NotImplementedError("Real DHT20 integration not implemented in scaffold.")
