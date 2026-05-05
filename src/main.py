from __future__ import annotations

import argparse
import time

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


def run_once(
    room_id: str = "bedroom_1",
    mqtt_enabled: bool = False,
    mqtt_host: str = "localhost",
    mqtt_port: int = 1883,
) -> dict:
    dht20 = DHT20Sensor(use_mock=True)
    scd30 = SCD30Sensor(use_mock=True)
    window_sensor = WindowSensor(use_mock=True)
    weather = WeatherAPI()

    predictor = Predictor(model_path="models/trained_model.pkl")
    simulator = ScenarioSimulator(predictor=predictor)
    decision_engine = DecisionEngine()

    logger = DataLogger(csv_path="data/raw/sensor_data.csv")
    sqlite_logger = SQLiteLogger(db_path="data/processed/observations.db")
    mqtt_client = MQTTClient(host=mqtt_host, port=mqtt_port, enabled=mqtt_enabled)

    dht_reading = dht20.read()
    co2_ppm = scd30.read_co2()
    window_open = window_sensor.is_open()
    weather_snapshot = weather.fetch_current()

    observation = Observation.from_sources(
        room_id=room_id,
        temperature_c=dht_reading.temperature_c,
        humidity_pct=dht_reading.humidity_pct,
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
        )
        print(f"Smart Ventilation result (cycle {cycle}):")
        for key, value in result.items():
            print(f"- {key}: {value}")

        if args.iterations == 0 or cycle < args.iterations:
            time.sleep(max(1, args.interval))
