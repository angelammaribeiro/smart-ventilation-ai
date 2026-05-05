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
WEATHER_LATITUDE = float(os.getenv("WEATHER_LATITUDE", "40.6405"))
WEATHER_LONGITUDE = float(os.getenv("WEATHER_LONGITUDE", "-8.6538"))
WEATHER_REFRESH_SECONDS = int(os.getenv("WEATHER_REFRESH_SECONDS", "300"))
WEATHER_API_TIMEOUT_SECONDS = float(os.getenv("WEATHER_API_TIMEOUT_SECONDS", "4"))
INDOOR_TEMP_UNIT = os.getenv("INDOOR_TEMP_UNIT", "auto").strip().lower()

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

_last_outdoor_weather: dict[str, float | None] = {
    "outdoor_temp_c": None,
    "outdoor_humidity_pct": None,
    "outdoor_pressure_hpa": None,
}
_last_outdoor_fetch_ts: float = 0.0


def get_state(entity_id: str) -> str:
    url = f"{HA_URL}/api/states/{entity_id}"
    response = requests.get(url, headers=headers, timeout=5)
    response.raise_for_status()
    return response.json()["state"]


def get_state_payload(entity_id: str) -> dict[str, Any]:
    url = f"{HA_URL}/api/states/{entity_id}"
    response = requests.get(url, headers=headers, timeout=5)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Invalid Home Assistant state payload")
    return payload


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


def _safe_get_state_payload(entity_id: str | None) -> dict[str, Any] | None:
    if not entity_id:
        return None
    try:
        payload = get_state_payload(entity_id)
    except Exception:
        return None

    state = str(payload.get("state", "")).strip().lower()
    if state in {"unknown", "unavailable", "none", ""}:
        return None
    return payload


def _to_celsius(value: float, unit: str | None) -> float:
    normalized = (unit or "").strip().lower().replace(" ", "")
    if normalized in {"°f", "f", "fahrenheit"}:
        return (value - 32.0) * (5.0 / 9.0)
    if normalized in {"°c", "c", "celsius"}:
        return value

    # Fallback when unit metadata is missing.
    if INDOOR_TEMP_UNIT in {"f", "fahrenheit"}:
        return (value - 32.0) * (5.0 / 9.0)
    if INDOOR_TEMP_UNIT in {"c", "celsius"}:
        return value

    # auto mode heuristic: indoor values above 60 are likely Fahrenheit.
    return (value - 32.0) * (5.0 / 9.0) if value > 60.0 else value


def _fetch_outdoor_weather() -> dict[str, float | None]:
    global _last_outdoor_fetch_ts

    now = time.time()
    cache_is_valid = (
        _last_outdoor_weather["outdoor_temp_c"] is not None
        and _last_outdoor_weather["outdoor_humidity_pct"] is not None
        and _last_outdoor_weather["outdoor_pressure_hpa"] is not None
        and (now - _last_outdoor_fetch_ts) < max(1, WEATHER_REFRESH_SECONDS)
    )
    if cache_is_valid:
        return dict(_last_outdoor_weather)

    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={WEATHER_LATITUDE}&longitude={WEATHER_LONGITUDE}"
        "&current=temperature_2m,relative_humidity_2m,surface_pressure"
    )
    try:
        response = requests.get(weather_url, timeout=WEATHER_API_TIMEOUT_SECONDS)
        response.raise_for_status()
        current = response.json().get("current", {})
        parsed = {
            "outdoor_temp_c": _to_float_or_none(str(current.get("temperature_2m"))),
            "outdoor_humidity_pct": _to_float_or_none(str(current.get("relative_humidity_2m"))),
            "outdoor_pressure_hpa": _to_float_or_none(str(current.get("surface_pressure"))),
        }
        if all(parsed[key] is not None for key in parsed):
            _last_outdoor_weather.update(parsed)
            _last_outdoor_fetch_ts = now
            return parsed

        # If response is malformed, keep last known good values.
        return dict(_last_outdoor_weather)
    except Exception:
        # Keep previously known outdoor values on transient API/network failure.
        return dict(_last_outdoor_weather)


def _build_payload() -> dict[str, Any]:
    temperature_payload = _safe_get_state_payload(ENTITIES.get("temperature"))
    temperature_state = temperature_payload.get("state") if temperature_payload else None
    temperature_unit = None
    if temperature_payload:
        attributes = temperature_payload.get("attributes", {})
        if isinstance(attributes, dict):
            temperature_unit = attributes.get("unit_of_measurement")

    humidity_state = _safe_get_state(ENTITIES.get("humidity"))
    pressure_state = _safe_get_state(ENTITIES.get("pressure"))
    motion_state = _safe_get_state(ENTITIES.get("motion"))
    window_state = _safe_get_state(ENTITIES.get("window"))
    outdoor = _fetch_outdoor_weather()

    indoor_temp_raw = _to_float_or_none(str(temperature_state) if temperature_state is not None else None)
    indoor_temp_c = _to_celsius(indoor_temp_raw, str(temperature_unit) if temperature_unit is not None else None) if indoor_temp_raw is not None else None

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": round(indoor_temp_c, 3) if indoor_temp_c is not None else None,
        "humidity_pct": _to_float_or_none(humidity_state),
        "pressure": _to_float_or_none(pressure_state),
        "outdoor_temp_c": outdoor["outdoor_temp_c"],
        "outdoor_humidity_pct": outdoor["outdoor_humidity_pct"],
        "outdoor_pressure_hpa": outdoor["outdoor_pressure_hpa"],
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
