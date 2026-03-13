#!/usr/bin/env python3
"""
gate-opener/app.py

Ascolta doorbell/aggregated: se la persona riconosciuta ha auto_open=true,
apre il cancello via c300x-controller API.
"""
import json
import os
import sqlite3
import urllib.request
from datetime import datetime

import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
DB_PATH = os.getenv("DB_PATH", "/shared_frames/faces.db")
UNLOCK_URL = os.getenv("UNLOCK_URL", "http://192.168.1.14:8080/unlock?id=default")
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.50"))


def _connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                name        TEXT PRIMARY KEY,
                auto_open   INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
    finally:
        conn.close()
    print(f"[gate-opener] DB pronto ({DB_PATH})")


def is_auto_open(name: str) -> bool:
    conn = _connect_db()
    try:
        row = conn.execute(
            "SELECT auto_open FROM persons WHERE name = ?", (name,)
        ).fetchone()
        return bool(row and row["auto_open"])
    finally:
        conn.close()


def unlock_gate() -> bool:
    try:
        req = urllib.request.Request(UNLOCK_URL)
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[gate-opener] Cancello aperto! ({resp.status})")
        return True
    except Exception as e:
        print(f"[gate-opener] Errore apertura cancello: {e}")
        return False


def on_connect(client, userdata, connect_flags, reason_code, properties):
    if not reason_code.is_failure:
        print(f"[gate-opener] MQTT connesso.")
        client.subscribe("doorbell/aggregated")
    else:
        print(f"[gate-opener] MQTT connessione fallita ({reason_code})")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[gate-opener] MQTT disconnesso inaspettatamente ({reason_code}), riconnessione automatica...")


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
        person = data.get("person")
        confidence = data.get("confidence", 0.0)
        ts = datetime.now().strftime("%H:%M:%S")

        if not person:
            print(f"[gate-opener] [{ts}] Persona sconosciuta, cancello chiuso")
            return

        if confidence < MIN_CONFIDENCE:
            print(f"[gate-opener] [{ts}] {person} confidence {confidence:.2f} < {MIN_CONFIDENCE}, cancello chiuso")
            return

        if is_auto_open(person):
            print(f"[gate-opener] [{ts}] {person} (confidence {confidence:.2f}) → APRO CANCELLO")
            unlock_gate()
        else:
            print(f"[gate-opener] [{ts}] {person} (confidence {confidence:.2f}) → auto_open disabilitato")

    except Exception as exc:
        print(f"[gate-opener] Errore: {exc}")


def main() -> None:
    init_db()

    conn = _connect_db()
    try:
        rows = conn.execute("SELECT name, auto_open FROM persons").fetchall()
    finally:
        conn.close()

    if rows:
        print(f"[gate-opener] Persone registrate:")
        for row in rows:
            flag = "AUTO-OPEN" if row["auto_open"] else "no"
            print(f"  - {row['name']}: {flag}")
    else:
        print(f"[gate-opener] Nessuna persona in tabella persons (usa la dashboard per configurare)")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    print("[gate-opener] In ascolto su doorbell/aggregated...")
    client.loop_forever()


if __name__ == "__main__":
    main()
