#!/usr/bin/env python3
"""
doorbell-trigger/app.py

Simula l'ESP32 del citofono.
Espone POST /ring  → pubblica evento MQTT su doorbell/events/ring.

Testabile con Postman: POST http://localhost:5001/ring
"""
import json
import os
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from flask import Flask, jsonify

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
DEVICE_ID = os.getenv("DEVICE_ID", "frontdoor")

app = Flask(__name__)

_mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
_mqtt_connected = False


def _on_connect(client, userdata, connect_flags, reason_code, properties):
    global _mqtt_connected
    if not reason_code.is_failure:
        _mqtt_connected = True
        print("[doorbell-trigger] MQTT connesso.")
    else:
        _mqtt_connected = False
        print(f"[doorbell-trigger] MQTT connessione fallita ({reason_code})")


def _on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    global _mqtt_connected
    _mqtt_connected = False
    if reason_code.is_failure:
        print(f"[doorbell-trigger] MQTT disconnesso ({reason_code}), riconnessione automatica...")


@app.route("/ring", methods=["POST"])
def ring():
    if not _mqtt_connected:
        return jsonify({"status": "error", "detail": "MQTT not connected"}), 503
    payload = {
        "event": "doorbell_pressed",
        "device_id": DEVICE_ID,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        _mqtt_client.publish("doorbell/events/ring", json.dumps(payload))
        print(f"[doorbell-trigger] Ring pubblicato: {payload}")
        return jsonify({"status": "ok", "payload": payload}), 200
    except Exception as exc:
        print(f"[doorbell-trigger] Errore MQTT: {exc}")
        return jsonify({"status": "error", "detail": str(exc)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "mqtt": _mqtt_connected}), 200


if __name__ == "__main__":
    _mqtt_client.on_connect = _on_connect
    _mqtt_client.on_disconnect = _on_disconnect
    _mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)
    _mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    _mqtt_client.loop_start()
    app.run(host="0.0.0.0", port=5001)
