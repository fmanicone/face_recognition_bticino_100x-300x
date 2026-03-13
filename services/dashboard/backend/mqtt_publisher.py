import json
import os

import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


def _on_connect(client, userdata, connect_flags, reason_code, properties):
    if not reason_code.is_failure:
        print("[dashboard] MQTT connesso.")
    else:
        print(f"[dashboard] MQTT connessione fallita: {reason_code}")


def start() -> None:
    _client.on_connect = _on_connect
    try:
        _client.connect_async(MQTT_HOST, MQTT_PORT, 60)
        _client.loop_start()
    except Exception as exc:
        print(f"[dashboard] MQTT non disponibile all'avvio: {exc}")


def publish_import(record_id: int, image_path: str, name: str) -> None:
    """Invia richiesta di import a face-recognition-service."""
    _client.publish(
        "faceid/import-requests",
        json.dumps({"record_id": record_id, "image_path": image_path, "name": name}),
    )


def publish_bulk_update(ids: list, fields: dict) -> None:
    """Delega aggiornamento campi a face-collector."""
    _client.publish(
        "faceid/db/bulk-update",
        json.dumps({"ids": ids, "fields": fields}),
    )


def publish_bulk_delete(ids: list) -> None:
    """Delega cancellazione record + file a face-collector."""
    _client.publish(
        "faceid/db/bulk-delete",
        json.dumps({"ids": ids, "delete_files": True}),
    )
