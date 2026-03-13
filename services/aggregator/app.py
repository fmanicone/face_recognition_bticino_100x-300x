#!/usr/bin/env python3
"""
aggregator/app.py

Ascolta faceid/results, raggruppa i risultati per session_id,
e pubblica il risultato finale su doorbell/aggregated quando:
- ha ricevuto abbastanza voti (MIN_VOTES) per una decisione anticipata, oppure
- ha ricevuto tutti i frame attesi (FRAMES_EXPECTED), oppure
- è scaduto il timeout (AGGREGATION_TIMEOUT_S secondi dall'ultimo frame)
"""
import json
import os
import threading
import time
from collections import defaultdict

import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.45"))
FRAMES_EXPECTED = int(os.getenv("FRAMES_EXPECTED", "4"))
AGGREGATION_TIMEOUT_S = int(os.getenv("AGGREGATION_TIMEOUT_S", "15"))
MIN_VOTES = int(os.getenv("MIN_VOTES", "2"))

sessions: dict = {}
sessions_lock = threading.Lock()

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


def decide(frames: list) -> tuple[str | None, float]:
    votes: dict[str, list[float]] = defaultdict(list)
    for frame in frames:
        if (
            frame.get("status") == "match"
            and frame.get("name")
            and float(frame.get("score", 0.0)) >= MATCH_THRESHOLD
        ):
            votes[frame["name"]].append(float(frame["score"]))

    if not votes:
        return None, 0.0

    best = max(votes, key=lambda n: (len(votes[n]), max(votes[n])))
    if len(votes[best]) >= MIN_VOTES:
        confidence = round(sum(votes[best]) / len(votes[best]), 4)
        return best, confidence

    return None, 0.0


def _publish_result(session_id: str, session: dict, reason: str) -> None:
    if session["finalized"]:
        return
    session["finalized"] = True
    frames = session["frames"]
    person, confidence = decide(frames)
    payload = {
        "session_id": session_id,
        "person": person,
        "confidence": confidence,
        "frames_received": len(frames),
        "status": "final",
    }
    mqtt_client.publish("doorbell/aggregated", json.dumps(payload))
    print(f"[aggregator] Risultato finale ({reason}): {payload}")


def timeout_watcher() -> None:
    while True:
        time.sleep(2)
        now = time.time()
        with sessions_lock:
            for sid, data in sessions.items():
                if data["finalized"]:
                    continue
                frames_done = len(data["frames"]) >= FRAMES_EXPECTED
                timed_out = (now - data["started_at"]) > AGGREGATION_TIMEOUT_S
                if frames_done:
                    _publish_result(sid, data, "all frames")
                elif timed_out:
                    _publish_result(sid, data, "timeout")


def on_connect(client, userdata, connect_flags, reason_code, properties):
    if not reason_code.is_failure:
        print(f"[aggregator] MQTT connesso (reason={reason_code}).")
        client.subscribe("faceid/results")
    else:
        print(f"[aggregator] MQTT connessione fallita (reason_code={reason_code})")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[aggregator] MQTT disconnesso inaspettatamente ({reason_code}), riconnessione automatica...")


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
        session_id = data.get("session_id")
        if not session_id:
            return

        with sessions_lock:
            if session_id not in sessions:
                sessions[session_id] = {
                    "frames": [],
                    "started_at": time.time(),
                    "finalized": False,
                }
            session = sessions[session_id]
            if session["finalized"]:
                return
            session["frames"].append(data)
            person, _ = decide(session["frames"])
            if person:
                _publish_result(session_id, session, "early")

        print(
            f"[aggregator] Ricevuto session={session_id} "
            f"frame={data.get('frame_index')} status={data.get('status')}"
        )
    except Exception as exc:
        print(f"[aggregator] Errore: {exc}")


def main() -> None:
    threading.Thread(target=timeout_watcher, daemon=True).start()

    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    print("[aggregator] In ascolto su faceid/results...")
    mqtt_client.loop_forever()


if __name__ == "__main__":
    main()
