from __future__ import annotations

import json

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

        if self._client is not None and username:
            self._client.username_pw_set(username, password or "")

    def connect(self) -> None:
        if self._client is None or self._connected:
            return
        try:
            self._client.connect(self.host, self.port, keepalive=30)
            self._client.loop_start()
            self._connected = True
        except Exception as exc:
            print(f"MQTT connect failed ({self.host}:{self.port}): {exc}")
            self._connected = False

    def publish_json(self, topic: str, payload: dict) -> None:
        if self._client is None:
            return
        self.connect()
        if not self._connected:
            return
        self._client.publish(topic, json.dumps(payload), qos=0)
