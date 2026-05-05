from __future__ import annotations

import json
import os
import socket
import time
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt
import requests

# ---------- CONFIG ----------
HA_URL = os.getenv("HA_URL", "http://192.168.93.63:8123")
HA_TOKEN = os.getenv("HA_TOKEN", "")

MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.93.63")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "mqtt_user")
MQTT_PASS = os.getenv("MQTT_PASS", "password")
MQTT_TOPIC_STATE = os.getenv("MQTT_TOPIC_STATE", "smart_room/telemetry/state")
MQTT_CONNECT_TIMEOUT_SECONDS = int(os.getenv("MQTT_CONNECT_TIMEOUT_SECONDS", "8"))

POLL_SECONDS = int(os.getenv("POLL_SECONDS", "5"))
WINDOW_ENTITY = os.getenv("WINDOW_ENTITY", "binary_sensor.lumi_lumi_sensor_magnet_aq2_opening")
WINDOW_OPEN_STATES = {
    state.strip().lower()
    for state in os.getenv("WINDOW_OPEN_STATES", "on,open,true,1").split(",")
    if state.strip()
}
WINDOW_CLOSED_STATES = {
    state.strip().lower()
    for state in os.getenv("WINDOW_CLOSED_STATES", "off,closed,false,0").split(",")
    if state.strip()
}

ENTITIES = {
    "temperature": "sensor.lumi_lumi_weather_temperature",
    "humidity": "sensor.lumi_lumi_weather_humidity",
    "pressure": "sensor.lumi_lumi_weather_pressure",
    "motion": "binary_sensor.lumi_lumi_sensor_motion_aq2_occupancy",
    # Optional entities; if not present they are published as null.
    "window": WINDOW_ENTITY,
}

# ---------- MQTT ----------
try:
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
except Exception:
    client = mqtt.Client()

client.username_pw_set(MQTT_USER, MQTT_PASS)

# ---------- HA REQUEST ----------
headers = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json",
}


def get_state(entity_id: str) -> str:
    url = f"{HA_URL}/api/states/{entity_id}"
    response = requests.get(url, headers=headers, timeout=5)
    response.raise_for_status()
    return response.json()["state"]


def _to_float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool_or_none(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = str(value).strip().lower()
    if lowered in {"on", "true", "1", "open"}:
        return True
    if lowered in {"off", "false", "0", "closed"}:
        return False
    return None


def _to_window_open_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = str(value).strip().lower()
    if lowered in WINDOW_OPEN_STATES:
        return True
    if lowered in WINDOW_CLOSED_STATES:
        return False
    return _to_bool_or_none(value)


def _safe_get_state(entity_id: str | None) -> str | None:
    if not entity_id:
        return None
    try:
        state = get_state(entity_id)
    except Exception:
        return None
    lowered = state.strip().lower()
    if lowered in {"unknown", "unavailable", "none", ""}:
        return None
    return state


def _build_payload() -> dict[str, Any]:
    temperature_state = _safe_get_state(ENTITIES.get("temperature"))
    humidity_state = _safe_get_state(ENTITIES.get("humidity"))
    pressure_state = _safe_get_state(ENTITIES.get("pressure"))
    motion_state = _safe_get_state(ENTITIES.get("motion"))
    window_state = _safe_get_state(ENTITIES.get("window"))

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": _to_float_or_none(temperature_state),
        "humidity_pct": _to_float_or_none(humidity_state),
        "pressure": _to_float_or_none(pressure_state),
        "motion": _to_bool_or_none(motion_state),
        "window_open": _to_window_open_bool(window_state),
    }


def _connect_mqtt() -> None:
    socket.setdefaulttimeout(MQTT_CONNECT_TIMEOUT_SECONDS)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except TimeoutError as exc:
        raise RuntimeError(
            "Timeout connecting to MQTT broker. Check broker IP/port reachability, "
            "network/VPN, and that Mosquitto is running. "
            f"Current MQTT_BROKER={MQTT_BROKER}, MQTT_PORT={MQTT_PORT}."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            "Could not connect to MQTT broker. Confirm host/IP, port, and firewall rules. "
            f"Current MQTT_BROKER={MQTT_BROKER}, MQTT_PORT={MQTT_PORT}."
        ) from exc


def main() -> None:
    if not HA_TOKEN:
        raise RuntimeError("HA_TOKEN is not set. Export HA_TOKEN before running this script.")

    _connect_mqtt()

    while True:
        try:
            payload = _build_payload()

            temp = payload["temperature_c"]
            hum = payload["humidity_pct"]
            window = payload["window_open"]
            motion = payload["motion"]

            client.publish(MQTT_TOPIC_STATE, json.dumps(payload), qos=0)

            if temp is not None:
                client.publish("smart_room/indoor/temperature", temp)
            if hum is not None:
                client.publish("smart_room/indoor/humidity", hum)
            if window is not None:
                client.publish("smart_room/window/open", int(window))
            if motion is not None:
                client.publish("smart_room/motion", int(motion))

            print("Published state:", payload)
        except Exception as exc:
            print("Erro:", exc)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
