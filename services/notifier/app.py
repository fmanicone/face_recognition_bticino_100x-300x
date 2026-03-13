#!/usr/bin/env python3
"""
notifier/app.py

Ascolta doorbell/aggregated e invia notifiche Telegram.
"""
import json
import os
import glob
import urllib.request
import urllib.parse
from datetime import datetime
from http.client import HTTPSConnection

import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SHARED_FRAMES_DIR = os.getenv("SHARED_FRAMES_DIR", "/shared_frames")


def on_connect(client, userdata, connect_flags, reason_code, properties):
    if not reason_code.is_failure:
        print(f"[notifier] MQTT connesso.")
        client.subscribe("doorbell/aggregated")
    else:
        print(f"[notifier] MQTT connessione fallita ({reason_code})")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[notifier] MQTT disconnesso inaspettatamente ({reason_code}), riconnessione automatica...")


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
        ts = datetime.now().strftime("%H:%M:%S")
        person = data.get("person")
        confidence = data.get("confidence", 0.0)
        session_id = data.get("session_id", "")

        if person:
            text = f"\U0001f514 Campanello\n\U0001f464 {person} (confidence {confidence:.0%})"
            print(f"[notifier] [{ts}] RICONOSCIUTO: {person} ({confidence:.2f})")
        else:
            text = f"\U0001f514 Campanello\n\u2753 Persona sconosciuta"
            print(f"[notifier] [{ts}] SCONOSCIUTO ({confidence:.2f})")

        photo_path = find_best_frame(session_id)
        if photo_path:
            send_telegram_photo(photo_path, text)
        else:
            send_telegram(text)

    except Exception as exc:
        print(f"[notifier] Errore: {exc}")


def find_best_frame(session_id: str) -> str | None:
    if not session_id:
        return None
    session_dir = os.path.join(SHARED_FRAMES_DIR, session_id)
    frames = glob.glob(os.path.join(session_dir, "frame_*.jpg"))
    if not frames:
        return None
    return max(frames, key=os.path.getsize)


def send_telegram_photo(photo_path: str, caption: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[notifier] Telegram non configurato, skip")
        return
    try:
        with open(photo_path, "rb") as f:
            photo_data = f.read()
    except (FileNotFoundError, OSError) as e:
        print(f"[notifier] Foto non trovata ({e}), invio solo testo")
        send_telegram(caption)
        return

    try:
        boundary = "----FormBoundary7MA4YWxkTrZu0gW"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
            f"{TELEGRAM_CHAT_ID}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n'
            f"{caption}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="doorbell.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode() + photo_data + f"\r\n--{boundary}--\r\n".encode()

        conn = HTTPSConnection("api.telegram.org", timeout=15)
        conn.request(
            "POST",
            f"/bot{TELEGRAM_TOKEN}/sendPhoto",
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        resp = conn.getresponse()
        print(f"[notifier] Telegram foto inviata ({resp.status})")
        conn.close()
    except Exception as e:
        print(f"[notifier] Telegram foto errore: {e}")
        send_telegram(caption)


def send_telegram(text: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[notifier] Telegram non configurato, skip")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
        }).encode()
        req = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[notifier] Telegram inviato ({resp.status})")
    except Exception as e:
        print(f"[notifier] Telegram errore: {e}")


def main() -> None:
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        print(f"[notifier] Telegram configurato (chat_id={TELEGRAM_CHAT_ID})")
    else:
        print(f"[notifier] ATTENZIONE: Telegram non configurato!")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    print("[notifier] In ascolto su doorbell/aggregated...")
    client.loop_forever()


if __name__ == "__main__":
    main()
