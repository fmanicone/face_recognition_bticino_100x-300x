#!/usr/bin/env python3
"""
doorbell-worker/app.py

BTicino C100X via c300x-controller RTSP:
- Quando arriva un ring event, cattura N frame via FFmpeg
- Pubblica su faceid/requests e camera/frames via MQTT
"""
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
RTSP_URL = os.getenv("RTSP_URL", "rtsp://192.168.1.14:6554/doorbell-video")
SHARED_FRAMES_DIR = os.getenv("SHARED_FRAMES_DIR", "/shared_frames")
DEVICE_ID = os.getenv("DEVICE_ID", "frontdoor")
FRAMES_TO_SAVE = int(os.getenv("FRAMES_TO_SAVE", 4))
FRAME_INTERVAL_S = float(os.getenv("FRAME_INTERVAL_S", "2.0"))

ring_event = threading.Event()
capturing = False


def on_connect(client, userdata, connect_flags, reason_code, properties):
    if not reason_code.is_failure:
        print(f"[doorbell-worker] MQTT connesso.")
        client.subscribe("doorbell/events/ring")
        client.subscribe("bticino/doorbell")
    else:
        print(f"[doorbell-worker] MQTT connessione fallita ({reason_code})")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[doorbell-worker] MQTT disconnesso inaspettatamente ({reason_code}), riconnessione automatica...")


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode(errors='replace').strip()

    if topic == "bticino/doorbell" and payload == "pressed":
        print(f"[doorbell-worker] RING from c300x-controller!")
        ring_event.set()
    elif topic == "doorbell/events/ring":
        print(f"[doorbell-worker] RING from trigger!")
        ring_event.set()


def generate_session_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return f"{DEVICE_ID}_{ts}"


def capture_frames(mqtt_client: mqtt.Client) -> None:
    global capturing
    capturing = True
    session_id = generate_session_id()
    session_dir = os.path.join(SHARED_FRAMES_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"[doorbell-worker] Cattura {FRAMES_TO_SAVE} frame → {session_dir}")

    saved = 0
    for i in range(FRAMES_TO_SAVE):
        path = os.path.join(session_dir, f"frame_{i}.jpg")
        cmd = [
            "ffmpeg", "-y",
            "-rtsp_transport", "tcp",
            "-timeout", "5000000",
            "-i", RTSP_URL,
            "-vframes", "1",
            "-q:v", "2",
            "-update", "1",
            path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=8)
            if result.returncode == 0 and os.path.exists(path):
                size = os.path.getsize(path)
                print(f"[doorbell-worker] Frame {i}: {path} ({size} bytes)")

                mqtt_client.publish("faceid/requests", json.dumps({
                    "session_id": session_id,
                    "frame_index": i,
                    "image_path": path,
                    "timestamp": timestamp,
                }))

                mqtt_client.publish("camera/frames", json.dumps({
                    "image_path": path,
                }))
                saved += 1
            else:
                stderr = result.stderr.decode(errors='replace')[-200:]
                print(f"[doorbell-worker] Frame {i} fallito: {stderr}")
        except subprocess.TimeoutExpired:
            print(f"[doorbell-worker] Frame {i} timeout")
        except Exception as e:
            print(f"[doorbell-worker] Frame {i} errore: {e}")

        if i < FRAMES_TO_SAVE - 1 and saved > 0:
            time.sleep(FRAME_INTERVAL_S)

    capturing = False
    print(f"[doorbell-worker] Sessione {session_id} completata ({saved}/{FRAMES_TO_SAVE} frame)")


def main() -> None:
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()

    print(f"[doorbell-worker] In attesa di ring events... (RTSP: {RTSP_URL})")

    while True:
        ring_event.wait()
        ring_event.clear()

        if capturing:
            print(f"[doorbell-worker] Cattura già in corso, ignoro ring")
            continue

        threading.Thread(
            target=capture_frames, args=(mqtt_client,), daemon=True
        ).start()


if __name__ == "__main__":
    main()
