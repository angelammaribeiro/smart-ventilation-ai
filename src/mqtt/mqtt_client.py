from __future__ import annotations

import json
import time

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None


class MQTTClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        enabled: bool = False,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.enabled = enabled and mqtt is not None
        self._client = mqtt.Client() if self.enabled else None
        self._connected = False
        self._connect_error: str | None = None

        if self._client is not None and username:
            self._client.username_pw_set(username, password or "")
        if self._client is not None:
            self._client.on_connect = self._on_connect

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:  # noqa: ANN001
        _ = client, userdata, flags, properties
        rc_value = getattr(reason_code, "value", reason_code)
        try:
            rc_int = int(rc_value)
        except (TypeError, ValueError):
            rc_int = -1

        if rc_int == 0:
            self._connected = True
            self._connect_error = None
        else:
            self._connected = False
            self._connect_error = str(reason_code)

    def connect(self) -> None:
        if self._client is None or self._connected:
            return
        try:
            self._connect_error = None
            self._connected = False
            rc = self._client.connect(self.host, self.port, keepalive=30)
            self._client.loop_start()

            mqtt_ok = getattr(mqtt, "MQTT_ERR_SUCCESS", 0)
            if rc == mqtt_ok:
                # connect() is blocking and successful on local brokers; mark connected immediately.
                self._connected = True
                return
            self._connect_error = f"rc={rc}"

            deadline = time.time() + 2.0
            while time.time() < deadline and not self._connected and self._connect_error is None:
                time.sleep(0.05)

            if not self._connected:
                if self._connect_error:
                    print(f"MQTT connect rejected ({self.host}:{self.port}): {self._connect_error}")
                else:
                    print(f"MQTT connect timeout ({self.host}:{self.port})")
        except Exception as exc:
            print(f"MQTT connect failed ({self.host}:{self.port}): {exc}")
            self._connected = False

    def publish_json(self, topic: str, payload: dict) -> None:
        if self._client is None:
            return
        self.connect()
        if not self._connected:
            return
        message = self._client.publish(topic, json.dumps(payload), qos=1)
        try:
            message.wait_for_publish(timeout=2.0)
        except Exception:
            pass

        rc = getattr(message, "rc", None)
        mqtt_ok = getattr(mqtt, "MQTT_ERR_SUCCESS", 0)
        if rc is not None and rc != mqtt_ok:
            print(f"MQTT publish failed topic={topic} rc={rc}")
