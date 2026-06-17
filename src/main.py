from __future__ import annotations

import argparse
import os
import time

import requests

from contracts.observation import Observation
from inference.decision_engine import DecisionEngine
from inference.predictor import Predictor
from inference.simulator import ScenarioSimulator
from logger.data_logger import DataLogger
from logger.sqlite_logger import SQLiteLogger
from mqtt.mqtt_client import MQTTClient
from sensors.dht20 import DHT20Sensor
from sensors.scd30 import SCD30Sensor
from sensors.window_sensor import WindowSensor
from weather.weather_api import WeatherAPI


def _ha_get_state(ha_url: str, ha_token: str, entity_id: str) -> dict:
    response = requests.get(
        f"{ha_url.rstrip('/')}/api/states/{entity_id}",
        headers={"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"},
        timeout=5,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid HA state payload for entity {entity_id}")
    return payload


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: object, default: bool = False) -> bool:
    lowered = str(value).strip().lower()
    if lowered in {"on", "open", "true", "1"}:
        return True
    if lowered in {"off", "closed", "false", "0"}:
        return False
    return default


def _to_celsius(value: float, unit: str | None) -> float:
    normalized = (unit or "").strip().lower().replace(" ", "")
    if normalized in {"°f", "f", "fahrenheit"}:
        return (value - 32.0) * (5.0 / 9.0)
    return value


def _estimate_co2_ppm(humidity_pct: float, motion: bool, window_open: bool) -> float:
    # In this source mode only CO2 is synthetic; all other values come from HA/weather.
    co2 = 560.0
    if motion:
        co2 += 220.0
    if not window_open:
        co2 += 200.0
    else:
        co2 -= 80.0

    co2 += max(0.0, (humidity_pct - 60.0) * 1.5)
    return max(420.0, min(1800.0, co2))


def run_once(
    room_id: str = "bedroom_1",
    mqtt_enabled: bool = False,
    mqtt_host: str = "localhost",
    mqtt_port: int = 1883,
    mqtt_user: str = "",
    mqtt_pass: str = "",
    data_source: str = "mock",
    ha_url: str = "",
    ha_token: str = "",
    ha_temp_entity: str = "sensor.lumi_lumi_weather_temperature",
    ha_humidity_entity: str = "sensor.lumi_lumi_weather_humidity",
    ha_motion_entity: str = "binary_sensor.lumi_lumi_sensor_motion_aq2_occupancy",
    ha_window_entity: str = "binary_sensor.lumi_lumi_sensor_magnet_aq2_2_opening",
) -> dict:
    use_mock = data_source != "ha"
    dht20 = DHT20Sensor(use_mock=use_mock)
    scd30 = SCD30Sensor(use_mock=use_mock)
    window_sensor = WindowSensor(use_mock=use_mock)
    weather = WeatherAPI()

    predictor = Predictor(model_path="models/trained_model.pkl")
    simulator = ScenarioSimulator(predictor=predictor)
    decision_engine = DecisionEngine()

    logger = DataLogger(csv_path="data/raw/sensor_data.csv")
    sqlite_logger = SQLiteLogger(db_path="data/processed/observations.db")
    mqtt_client = MQTTClient(
        host=mqtt_host,
        port=mqtt_port,
        enabled=mqtt_enabled,
        username=mqtt_user,
        password=mqtt_pass,
    )

    weather_snapshot = weather.fetch_current()

    if data_source == "ha":
        if not ha_url or not ha_token:
            raise RuntimeError("HA source selected but HA URL/token is missing. Use --ha-url and --ha-token.")

        temp_payload = _ha_get_state(ha_url, ha_token, ha_temp_entity)
        hum_payload = _ha_get_state(ha_url, ha_token, ha_humidity_entity)
        motion_payload = _ha_get_state(ha_url, ha_token, ha_motion_entity)
        window_payload = _ha_get_state(ha_url, ha_token, ha_window_entity)

        temp_state = _to_float(temp_payload.get("state"), default=0.0)
        temp_unit = None
        attributes = temp_payload.get("attributes")
        if isinstance(attributes, dict):
            temp_unit = attributes.get("unit_of_measurement")

        temperature_c = _to_celsius(temp_state, str(temp_unit) if temp_unit is not None else None)
        humidity_pct = _to_float(hum_payload.get("state"), default=50.0)
        motion_now = _to_bool(motion_payload.get("state"), default=False)
        window_open = _to_bool(window_payload.get("state"), default=False)
        co2_ppm = _estimate_co2_ppm(humidity_pct=humidity_pct, motion=motion_now, window_open=window_open)
    else:
        dht_reading = dht20.read()
        temperature_c = dht_reading.temperature_c
        humidity_pct = dht_reading.humidity_pct
        co2_ppm = scd30.read_co2()
        window_open = window_sensor.is_open()

    observation = Observation.from_sources(
        room_id=room_id,
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
        co2_ppm=co2_ppm,
        window_open=window_open,
        temp_out=weather_snapshot.temp_out,
        humidity_out=weather_snapshot.humidity_out,
        wind_speed=weather_snapshot.wind_speed,
        is_raining=bool(weather_snapshot.is_raining),
    )
    scenario = simulator.evaluate(observation)

    decision = decision_engine.decide(
        co2_now=observation.co2_ppm,
        window_open_now=bool(observation.window_open),
        pred_co2_closed=scenario.pred_co2_closed,
        pred_temp_closed=scenario.pred_temp_closed,
        pred_co2_open=scenario.pred_co2_open,
        pred_temp_open=scenario.pred_temp_open,
        temp_now=observation.temperature_c,
        temp_out_now=observation.temp_out,
        is_raining_now=bool(observation.is_raining),
    )

    row = observation.to_dict()
    row.update(
        {
            "pred_co2_closed": round(scenario.pred_co2_closed, 2),
            "pred_temp_closed": round(scenario.pred_temp_closed, 2),
            "pred_co2_open": round(scenario.pred_co2_open, 2),
            "pred_temp_open": round(scenario.pred_temp_open, 2),
            "action": decision.action,
            "reason": decision.reason,
        }
    )

    logger.append(row)
    sqlite_logger.append(row)
    mqtt_client.publish_json("smart_ventilation/telemetry", row)

    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart Ventilation AI runtime")
    parser.add_argument("--room-id", default="bedroom_1")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between cycles")
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of cycles to run. Use 0 for continuous run.",
    )
    parser.add_argument("--mqtt-enabled", action="store_true")
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--mqtt-user", default="")
    parser.add_argument("--mqtt-pass", default="")
    parser.add_argument("--data-source", choices=["mock", "ha"], default=os.getenv("DATA_SOURCE", "mock"))
    parser.add_argument("--ha-url", default=os.getenv("HA_URL", ""))
    parser.add_argument("--ha-token", default=os.getenv("HA_TOKEN", ""))
    parser.add_argument("--ha-temp-entity", default=os.getenv("HA_TEMP_ENTITY", "sensor.lumi_lumi_weather_temperature"))
    parser.add_argument("--ha-humidity-entity", default=os.getenv("HA_HUMIDITY_ENTITY", "sensor.lumi_lumi_weather_humidity"))
    parser.add_argument("--ha-motion-entity", default=os.getenv("HA_MOTION_ENTITY", "binary_sensor.lumi_lumi_sensor_motion_aq2_occupancy"))
    parser.add_argument("--ha-window-entity", default=os.getenv("HA_WINDOW_ENTITY", "binary_sensor.lumi_lumi_sensor_magnet_aq2_2_opening"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cycle = 0

    while args.iterations == 0 or cycle < args.iterations:
        cycle += 1
        result = run_once(
            room_id=args.room_id,
            mqtt_enabled=args.mqtt_enabled,
            mqtt_host=args.mqtt_host,
            mqtt_port=args.mqtt_port,
            mqtt_user=args.mqtt_user,
            mqtt_pass=args.mqtt_pass,
            data_source=args.data_source,
            ha_url=args.ha_url,
            ha_token=args.ha_token,
            ha_temp_entity=args.ha_temp_entity,
            ha_humidity_entity=args.ha_humidity_entity,
            ha_motion_entity=args.ha_motion_entity,
            ha_window_entity=args.ha_window_entity,
        )
        print(f"Smart Ventilation result (cycle {cycle}):")
        for key, value in result.items():
            print(f"- {key}: {value}")

        if args.iterations == 0 or cycle < args.iterations:
            time.sleep(max(1, args.interval))
