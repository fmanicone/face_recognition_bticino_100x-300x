import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

import db

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
FRAME_COOLDOWN_S = float(os.getenv("FRAME_COOLDOWN_S", "2.5"))
SESSION_MAX_FRAMES = int(os.getenv("SESSION_MAX_FRAMES", "4"))
SESSION_RESET_S = float(os.getenv("SESSION_RESET_S", "5.0"))


_lock = threading.Lock()
_session_id = str(uuid.uuid4())
_session_frame_count = 0
_last_save_time = 0.0
_last_face_time = 0.0


def handle_camera_frame(client, payload_bytes: bytes) -> None:
    global _session_id, _session_frame_count, _last_save_time, _last_face_time

    try:
        data = json.loads(payload_bytes)
        image_path = data["image_path"]
    except Exception as exc:
        print(f"[collector] Errore decode payload: {exc}")
        return

    now = time.time()

    with _lock:
        if _last_face_time > 0 and now - _last_face_time > SESSION_RESET_S:
            _session_id = str(uuid.uuid4())
            _session_frame_count = 0
            _last_face_time = 0.0
            print(f"[collector] Nuova sessione: {_session_id[:8]}...")

        if (
            _session_frame_count >= SESSION_MAX_FRAMES
            or now - _last_save_time < FRAME_COOLDOWN_S
        ):
            try:
                os.remove(image_path)
            except OSError:
                pass
            return

        session_id = _session_id
        frame_index = _session_frame_count
        _session_frame_count += 1
        _last_save_time = now
        _last_face_time = now

    detected_at = datetime.now(timezone.utc).isoformat()
    record_id = db.insert_face(image_path, detected_at, session_id)

    print(
        f"[collector] Frame accettato: {os.path.basename(image_path)} "
        f"(sessione {session_id[:8]}..., {frame_index + 1}/{SESSION_MAX_FRAMES})"
    )

    client.publish(
        "faceid/collector/match-requests",
        json.dumps(
            {"record_id": record_id, "image_path": image_path, "session_id": session_id}
        ),
    )


def handle_match_result(payload_bytes: bytes) -> None:
    global _last_face_time

    try:
        data = json.loads(payload_bytes)
        record_id = data["record_id"]
        no_face = data.get("no_face", False)

        if no_face:
            db.delete_face(record_id, delete_file=True)
            print(f"[collector] Nessun volto — record {record_id} rimosso.")
        else:
            name = data.get("name")
            score = data.get("score")
            db.update_face(
                record_id, {"suggested_name": name, "suggested_score": score}
            )
            with _lock:
                _last_face_time = time.time()
            print(
                f"[collector] Match: record_id={record_id}, name={name}, score={score}"
            )

    except Exception as exc:
        print(f"[collector] Errore handle_match_result: {exc}")


def handle_db_update(payload_bytes: bytes) -> None:
    """faceid/db/update  →  { "record_id": int, "fields": { col: val, ... } }"""
    try:
        data = json.loads(payload_bytes)
        db.update_face(data["record_id"], data["fields"])
        print(f"[collector] DB update record_id={data['record_id']} {data['fields']}")
    except Exception as exc:
        print(f"[collector] Errore handle_db_update: {exc}")


def handle_db_delete(payload_bytes: bytes) -> None:
    """faceid/db/delete  →  { "record_id": int, "delete_file": bool }"""
    try:
        data = json.loads(payload_bytes)
        db.delete_face(data["record_id"], data.get("delete_file", True))
        print(f"[collector] DB delete record_id={data['record_id']}")
    except Exception as exc:
        print(f"[collector] Errore handle_db_delete: {exc}")


def handle_db_bulk_update(payload_bytes: bytes) -> None:
    """faceid/db/bulk-update  →  { "ids": [int, ...], "fields": { col: val, ... } }"""
    try:
        data = json.loads(payload_bytes)
        db.bulk_update(data["ids"], data["fields"])
        print(
            f"[collector] DB bulk-update {len(data['ids'])} record(s) {data['fields']}"
        )
    except Exception as exc:
        print(f"[collector] Errore handle_db_bulk_update: {exc}")


def handle_db_bulk_delete(payload_bytes: bytes) -> None:
    """faceid/db/bulk-delete  →  { "ids": [int, ...], "delete_files": bool }"""
    try:
        data = json.loads(payload_bytes)
        ids = data["ids"]
        db.bulk_delete(ids, data.get("delete_files", True))
        print(f"[collector] DB bulk-delete {len(ids)} record(s)")
    except Exception as exc:
        print(f"[collector] Errore handle_db_bulk_delete: {exc}")


def on_connect(client, userdata, connect_flags, reason_code, properties):
    if not reason_code.is_failure:
        print("[collector] MQTT connesso.")
        client.subscribe("camera/frames")
        client.subscribe("faceid/collector/match-results")
        client.subscribe("faceid/db/update")
        client.subscribe("faceid/db/delete")
        client.subscribe("faceid/db/bulk-update")
        client.subscribe("faceid/db/bulk-delete")
    else:
        print(f"[collector] MQTT connessione fallita: {reason_code}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[collector] MQTT disconnesso inaspettatamente ({reason_code}), riconnessione automatica...")


def on_message(client, userdata, msg):
    if msg.topic == "camera/frames":
        handle_camera_frame(client, msg.payload)
    elif msg.topic == "faceid/collector/match-results":
        handle_match_result(msg.payload)
    elif msg.topic == "faceid/db/update":
        handle_db_update(msg.payload)
    elif msg.topic == "faceid/db/delete":
        handle_db_delete(msg.payload)
    elif msg.topic == "faceid/db/bulk-update":
        handle_db_bulk_update(msg.payload)
    elif msg.topic == "faceid/db/bulk-delete":
        handle_db_bulk_delete(msg.payload)


def main() -> None:
    db.init_db()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    print(
        "[collector] In ascolto su camera/frames, faceid/collector/match-results, faceid/db/*..."
    )
    client.loop_forever()


if __name__ == "__main__":
    main()
