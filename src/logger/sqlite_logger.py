from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict


class SQLiteLogger:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    timestamp TEXT NOT NULL,
                    room_id TEXT NOT NULL,
                    temperature_c REAL NOT NULL,
                    humidity_pct REAL NOT NULL,
                    co2_ppm REAL NOT NULL,
                    window_open INTEGER NOT NULL,
                    temp_out REAL NOT NULL,
                    humidity_out REAL NOT NULL,
                    wind_speed REAL NOT NULL,
                    is_raining INTEGER NOT NULL,
                    hour_of_day INTEGER NOT NULL,
                    pred_co2_closed REAL,
                    pred_temp_closed REAL,
                    pred_co2_open REAL,
                    pred_temp_open REAL,
                    action TEXT,
                    reason TEXT,
                    PRIMARY KEY(timestamp, room_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_observations_ts ON observations(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_observations_room ON observations(room_id)"
            )

    def append(self, row: Dict[str, Any]) -> None:
        columns = [
            "timestamp",
            "room_id",
            "temperature_c",
            "humidity_pct",
            "co2_ppm",
            "window_open",
            "temp_out",
            "humidity_out",
            "wind_speed",
            "is_raining",
            "hour_of_day",
            "pred_co2_closed",
            "pred_temp_closed",
            "pred_co2_open",
            "pred_temp_open",
            "action",
            "reason",
        ]
        values = [row.get(column) for column in columns]
        placeholders = ",".join(["?" for _ in columns])

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO observations ({','.join(columns)}) VALUES ({placeholders})",
                values,
            )
