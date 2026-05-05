from __future__ import annotations

import random


class WindowSensor:
    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock

    def is_open(self) -> bool:
        if self.use_mock:
            return random.choice([True, False])
        raise NotImplementedError("Real window sensor integration not implemented in scaffold.")
