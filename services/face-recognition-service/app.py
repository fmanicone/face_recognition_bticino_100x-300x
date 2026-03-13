#!/usr/bin/env python3
"""
face-recognition-service/app.py

Ascolta 3 topic MQTT:
  - faceid/requests                   → match per ring event (doorbell-worker)
  - faceid/collector/match-requests   → match per frame continui (face-collector)
  - faceid/import-requests            → import nel FAISS (richiesto dalla dashboard)
"""
import json
import os
import threading

import cv2
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

print("[faceid-service] Inizializzazione pipeline...")
from faceid.pipeline import FacePipeline
from faceid.repositories.faiss_repo import FaissVectorRepository
from faceid.repositories.sqlite_repo import SqliteMetadataRepository
from faceid.services.import_service import ImportService
from faceid.services.match_service import MatchService

pipeline = FacePipeline()
vector_repo = FaissVectorRepository()
metadata_repo = SqliteMetadataRepository()
match_service = MatchService(pipeline, vector_repo, metadata_repo)
import_service = ImportService(pipeline, vector_repo, metadata_repo)

_import_lock = threading.Lock()

print("[faceid-service] Pipeline pronta.")

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


def _db_update(client, record_id: int, fields: dict) -> None:
    client.publish(
        "faceid/db/update", json.dumps({"record_id": record_id, "fields": fields})
    )


def _db_delete(client, record_id: int) -> None:
    client.publish(
        "faceid/db/delete", json.dumps({"record_id": record_id, "delete_file": True})
    )


def handle_ring_match(client, data: dict) -> None:
    session_id = data.get("session_id")
    frame_index = data.get("frame_index")
    image_path = data.get("image_path")
    print(f"[faceid-service] Ring match: session={session_id} frame={frame_index}")

    img = cv2.imread(image_path)
    if img is None:
        payload = {
            "session_id": session_id,
            "frame_index": frame_index,
            "name": None,
            "score": 0.0,
            "status": "error",
        }
    else:
        result = match_service.execute_frame(img)
        payload = {
            "session_id": session_id,
            "frame_index": frame_index,
            "name": result.name if result.matched else None,
            "score": round(float(result.score), 4),
            "status": "match" if result.matched else "unknown",
        }
    client.publish("faceid/results", json.dumps(payload))
    print(f"[faceid-service] Ring result: {payload}")


def handle_collector_match(client, data: dict) -> None:
    record_id = data.get("record_id")
    image_path = data.get("image_path")
    session_id = data.get("session_id")

    img = cv2.imread(image_path)
    if img is None:
        _db_delete(client, record_id)
        print(
            f"[faceid-service] Collector: frame illeggibile, scartato (record_id={record_id})"
        )
        return

    faces = pipeline.app.get(img)
    if not faces:
        client.publish(
            "faceid/collector/match-results",
            json.dumps(
                {"record_id": record_id, "session_id": session_id, "no_face": True}
            ),
        )
        return

    result = match_service.execute_frame(img)
    client.publish(
        "faceid/collector/match-results",
        json.dumps(
            {
                "record_id": record_id,
                "session_id": session_id,
                "no_face": False,
                "name": result.name,
                "score": round(float(result.score), 4),
                "matched": result.matched,
            }
        ),
    )
    print(
        f"[faceid-service] Collector match: record_id={record_id}, name={result.name}, score={result.score:.3f}"
    )


def handle_import_request(client, data: dict) -> None:
    record_id = data.get("record_id")
    image_path = data.get("image_path")
    name = data.get("name")

    if not image_path or not name:
        client.publish(
            "faceid/import-results",
            json.dumps(
                {
                    "record_id": record_id,
                    "success": False,
                    "error": "image_path o name mancante",
                }
            ),
        )
        return

    with _import_lock:
        result = import_service.execute(image_path, name, quality_check=False)

    if result.success:
        _db_delete(client, record_id)
    else:
        _db_update(
            client, record_id, {"status": "pending"}
        )

    client.publish(
        "faceid/import-results",
        json.dumps(
            {"record_id": record_id, "success": result.success, "error": result.error}
        ),
    )
    print(f"[faceid-service] Import: record_id={record_id}, success={result.success}")


def on_connect(client, userdata, connect_flags, reason_code, properties):
    if not reason_code.is_failure:
        print(f"[faceid-service] MQTT connesso.")
        client.subscribe("faceid/requests")
        client.subscribe("faceid/collector/match-requests")
        client.subscribe("faceid/import-requests")
    else:
        print(f"[faceid-service] MQTT connessione fallita: {reason_code}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[faceid-service] MQTT disconnesso inaspettatamente ({reason_code}), riconnessione automatica...")


_active_threads: list[threading.Thread] = []
_threads_lock = threading.Lock()


def _tracked_thread(target, args) -> None:
    t = threading.Thread(target=target, args=args)
    with _threads_lock:
        _active_threads.append(t)
    t.start()
    with _threads_lock:
        _active_threads[:] = [th for th in _active_threads if th.is_alive()]


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
        if msg.topic == "faceid/requests":
            _tracked_thread(handle_ring_match, (client, data))
        elif msg.topic == "faceid/collector/match-requests":
            _tracked_thread(handle_collector_match, (client, data))
        elif msg.topic == "faceid/import-requests":
            _tracked_thread(handle_import_request, (client, data))
    except Exception as exc:
        print(f"[faceid-service] Errore: {exc}")


def _shutdown() -> None:
    with _threads_lock:
        pending = list(_active_threads)
    if pending:
        print(f"[faceid-service] Shutdown: attendo {len(pending)} thread...")
        for t in pending:
            t.join(timeout=10)


import atexit
atexit.register(_shutdown)


def main() -> None:
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    print(
        "[faceid-service] In ascolto su faceid/requests, faceid/collector/match-requests, faceid/import-requests..."
    )
    mqtt_client.loop_forever()


if __name__ == "__main__":
    main()
