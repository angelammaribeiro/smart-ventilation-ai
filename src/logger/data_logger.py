from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Any


class DataLogger:
    def __init__(self, csv_path: str) -> None:
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, row: Dict[str, Any]) -> None:
        file_exists = self.csv_path.exists() and self.csv_path.stat().st_size > 0
        fieldnames = list(row.keys())

        with self.csv_path.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
