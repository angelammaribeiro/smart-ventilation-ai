from __future__ import annotations

import random


class SCD30Sensor:
    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock

    def read_co2(self) -> float:
        if self.use_mock:
            return round(random.uniform(550.0, 1500.0), 1)
        raise NotImplementedError("Real SCD30 integration not implemented in scaffold.")
