from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt


class TelemetryCollector:
    def __init__(self, csv_path: str, topic: str, window_label_mode: str, window_label_file: str) -> None:
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.topic = topic
        self.window_label_mode = window_label_mode
        self.window_label_file = Path(window_label_file)
        self.fieldnames = [
            "timestamp",
            "temperature_c",
            "humidity_pct",
            "pressure",
            "outdoor_temp_c",
            "outdoor_humidity_pct",
            "outdoor_pressure_hpa",
            "motion",
            "window_open",
            "window_open_source",
        ]

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {key: payload.get(key) for key in self.fieldnames}
        window_value = payload.get("window_open")
        source = "payload" if window_value is not None else "missing"

        manual_window = self._read_manual_window_state()
        if self.window_label_mode == "manual-only":
            window_value = manual_window
            source = "manual" if manual_window is not None else "missing"
        elif self.window_label_mode == "payload-else-manual":
            if window_value is None and manual_window is not None:
                window_value = manual_window
                source = "manual"

        row["window_open"] = window_value
        row["window_open_source"] = source
        return row

    def _read_manual_window_state(self) -> bool | None:
        if not self.window_label_file.exists():
            return None

        try:
            payload = json.loads(self.window_label_file.read_text(encoding="utf-8"))
            raw = payload.get("window_open")
        except Exception:
            return None

        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return bool(int(raw))
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"1", "true", "on", "open"}:
                return True
            if lowered in {"0", "false", "off", "closed"}:
                return False
        return None

    def _append_row(self, row: dict[str, Any]) -> None:
        file_exists = self.csv_path.exists() and self.csv_path.stat().st_size > 0
        if file_exists:
            with self.csv_path.open("r", newline="", encoding="utf-8") as csv_file:
                reader = csv.reader(csv_file)
                existing_header = next(reader, [])
            if existing_header != self.fieldnames:
                raise RuntimeError(
                    "CSV header does not match current schema. "
                    "Backup/remove the CSV and restart collector to create a new header."
                )

        with self.csv_path.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=self.fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    @staticmethod
    def _normalize_reason_code(reason_code: Any) -> tuple[int | None, str]:
        reason_text = str(reason_code)
        value = getattr(reason_code, "value", None)
        if isinstance(value, (int, float)):
            return int(value), reason_text
        if isinstance(reason_code, (int, float)):
            return int(reason_code), reason_text
        try:
            return int(reason_text), reason_text
        except (TypeError, ValueError):
            return None, reason_text

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: dict[str, Any],
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        _ = userdata, flags, properties
        rc_value, reason_text = self._normalize_reason_code(reason_code)
        reason_text_lc = reason_text.lower()

        is_success = rc_value == 0 or reason_text_lc in {"success", "0"}
        if not is_success:
            if rc_value == 5 or "not authorized" in reason_text_lc:
                print("MQTT auth failed (reason_code=5). Check --mqtt-user and --mqtt-pass.")
            else:
                print(f"MQTT connection failed with reason_code={reason_text}")
            client.disconnect()
            return

        print("MQTT connected")
        client.subscribe(self.topic)
        print(f"Subscribed to topic: {self.topic}")

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        _ = client, userdata
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if not isinstance(payload, dict):
                return
            row = self._normalize(payload)
            self._append_row(row)
            print("Saved telemetry row:", row)
        except Exception as exc:
            print("Failed to process message:", exc)

    def run(self, host: str, port: int, username: str, password: str) -> None:
        try:
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                reconnect_on_failure=False,
            )
        except Exception:
            client = mqtt.Client()
        if username:
            client.username_pw_set(username, password)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect(host, port, 60)
        client.loop_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect HA telemetry from MQTT into CSV")
    parser.add_argument("--csv-path", default="data/raw/ha_telemetry.csv")
    parser.add_argument("--topic", default="smart_room/telemetry/state")
    parser.add_argument("--mqtt-host", default=os.getenv("MQTT_BROKER", "172.20.10.3"))
    parser.add_argument("--mqtt-port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--mqtt-user", default=os.getenv("MQTT_USER", ""))
    parser.add_argument("--mqtt-pass", default=os.getenv("MQTT_PASS", ""))
    parser.add_argument(
        "--window-label-mode",
        choices=["payload", "manual-only", "payload-else-manual"],
        default="payload",
        help="How to define window_open in saved telemetry.",
    )
    parser.add_argument(
        "--window-label-file",
        default="data/processed/manual_window_state.json",
        help="JSON file with manual window state, e.g. {\"window_open\": true}",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    collector = TelemetryCollector(
        csv_path=args.csv_path,
        topic=args.topic,
        window_label_mode=args.window_label_mode,
        window_label_file=args.window_label_file,
    )
    collector.run(
        host=args.mqtt_host,
        port=args.mqtt_port,
        username=args.mqtt_user,
        password=args.mqtt_pass,
    )
