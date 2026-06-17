from __future__ import annotations

import random


class WindowSensor:
    _mock_is_open: bool | None = None

    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock

    def is_open(self) -> bool:
        if self.use_mock:
            if WindowSensor._mock_is_open is None:
                WindowSensor._mock_is_open = random.choice([True, False])
            else:
                # Keep state stable; occasional toggle simulates a user action.
                if random.random() < 0.08:
                    WindowSensor._mock_is_open = not WindowSensor._mock_is_open

            return WindowSensor._mock_is_open
        raise NotImplementedError("Real window sensor integration not implemented in scaffold.")
