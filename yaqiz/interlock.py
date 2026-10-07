"""Signal to the operator of nearby equipment when someone enters an interlocked zone.

Simulated by default (recorded on the event and shown in the dashboard). With YAQIZ_MQTT_URL set,
a JSON message is published to `yaqiz/zones/<id>/operator` (QoS 1), e.g. for a cab buzzer or tablet.
Automatic machine stopping is deliberately out of scope until it has an engineering sign-off.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse


class Interlock:
    def __init__(self, mqtt_url: str = "") -> None:
        self.url = mqtt_url.strip()
        self._client = None
        self._lock = threading.Lock()

    def _connect(self):  # noqa: ANN202
        import paho.mqtt.client as mqtt

        u = urlparse(self.url)
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="yaqiz")
        if u.username:
            client.username_pw_set(u.username, u.password)
        client.connect(u.hostname or "127.0.0.1", u.port or 1883, keepalive=30)
        client.loop_start()
        return client

    def signal(self, zone_id: int, zone_name: str | None, camera_id: int, kind: str) -> dict:
        topic = f"yaqiz/zones/{zone_id}/operator"
        payload = {"cmd": "warn_operator", "zone_id": zone_id, "zone_name": zone_name, "camera_id": camera_id,
                   "kind": kind, "ts": datetime.now(timezone.utc).isoformat()}
        if not self.url:
            return {"mode": "simulated", "topic": topic, "ok": True}
        try:
            with self._lock:
                if self._client is None:
                    self._client = self._connect()
                info = self._client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
            return {"mode": "mqtt", "topic": topic, "ok": info.rc == 0}
        except Exception as exc:  # noqa: BLE001
            return {"mode": "mqtt", "topic": topic, "ok": False, "error": str(exc)}
