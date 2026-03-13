# Face Recognition for BTicino Classe 300X/100X

## About This Project

This project adds **AI-powered face recognition** to the BTicino Classe 300X (or C100X) video intercom. When someone rings the doorbell, the system captures their face from the intercom camera, identifies them using deep learning, sends a Telegram notification with the visitor's photo and name, and can **automatically unlock the door** for authorized people — all in about 6-7 seconds.

### Key Features

- **Real-time face recognition** using InsightFace (ArcFace) with FAISS vector search
- **Automatic door unlock** for registered and authorized people
- **Telegram notifications** with visitor photo, name, and confidence score
- **Web dashboard** to manage faces, assign names, and configure auto-open
- **Multi-frame voting** — 4 frames are analyzed per event, requiring 2+ matches for a decision
- **Quality filtering** — rejects blurry, side-profile, or distant faces automatically
- **Fully containerized** — 9 Docker microservices communicating via MQTT

### How It Works

The system is built as an event-driven microservice architecture. An MQTT message bus decouples all services, making the system modular and resilient.

```
                         BTicino Intercom (on the wall)
                    ┌──────────────────────────────────────┐
                    │  Custom firmware + c300x-controller   │
                    │  ┌─────────┐  ┌─────────┐  ┌──────┐ │
                    │  │  RTSP   │  │  HTTP   │  │ MQTT │ │
                    │  │ :6554   │  │ :8080   │  │client│ │
                    │  └────┬────┘  └────▲────┘  └──┬───┘ │
                    └───────┼────────────┼──────────┼──────┘
                            │            │          │
                      video │     unlock │   ring   │
                     stream │    command │   event  │
                            │            │          │
  ══════════════════════════╪════════════╪══════════╪══════════ LAN
                            │            │          │
                    ┌───────┼────────────┼──────────┼──────┐
                    │       ▼            │          ▼      │
                    │  ┌─────────┐       │   ┌──────────┐  │
                    │  │doorbell-│       │   │mosquitto │  │
                    │  │ worker  │       │   │  (MQTT)  │  │
                    │  └────┬────┘       │   └──┬───┬───┘  │
                    │       │ 4 frames   │      │   │      │
                    │       ▼            │      │   │      │
                    │  ┌──────────────┐  │      │   │      │
                    │  │    face-     │  │      │   │      │
                    │  │ recognition  │◄─┼──────┘   │      │
                    │  │ (InsightFace │  │          │      │
                    │  │  + FAISS)    │  │          │      │
                    │  └──────┬───────┘  │          │      │
                    │         │ results  │          │      │
                    │         ▼          │          │      │
                    │  ┌──────────────┐  │          │      │
                    │  │  aggregator  │  │          │      │
                    │  │ (2/4 votes)  │  │          │      │
                    │  └──┬───────┬───┘  │          │      │
                    │     │       │      │          │      │
                    │     ▼       ▼      │          │      │
                    │ ┌────────┐ ┌───────┴──┐       │      │
                    │ │notifier│ │  gate-   │       │      │
                    │ │(Telegr)│ │  opener  │       │      │
                    │ └────────┘ └──────────┘       │      │
                    │                               │      │
                    │ ┌──────────┐  ┌────────────┐  │      │
                    │ │dashboard │  │   face-    │◄─┘      │
                    │ │  :5050   │  │ collector  │         │
                    │ └──────────┘  └────────────┘         │
                    │         Server (Docker)               │
                    └──────────────────────────────────────┘
```

### Recognition Pipeline

```
 Doorbell ring
      │
      ▼
 ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
 │  1. CAPTURE      │     │  2. DETECT        │     │  3. EMBED        │
 │  4 frames from   │────▶│  InsightFace      │────▶│  ArcFace ResNet  │
 │  RTSP stream     │     │  SCRFD model      │     │  512-dim vector  │
 │  (1s apart)      │     │  face detection   │     │  L2-normalized   │
 └─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                            │
                                                            ▼
 ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
 │  6. DECIDE       │     │  5. AGGREGATE     │     │  4. SEARCH       │
 │  Notify via      │◀────│  Vote across 4    │◀────│  FAISS cosine    │
 │  Telegram +      │     │  frames (need     │     │  similarity      │
 │  auto-unlock     │     │  2+ matches)      │     │  top-10 nearest  │
 └─────────────────┘     └──────────────────┘     └─────────────────┘
```

### MQTT Topic Map

| Topic | Publisher | Subscriber | Payload |
|-------|-----------|------------|---------|
| `bticino/doorbell` | c300x-controller | doorbell-worker | `"pressed"` |
| `faceid/requests` | doorbell-worker | face-recognition | session + frame paths |
| `faceid/results` | face-recognition | aggregator | name + score per frame |
| `doorbell/aggregated` | aggregator | notifier, gate-opener | final decision |
| `camera/frames` | doorbell-worker | face-collector | continuous frame stream |
| `faceid/import-requests` | dashboard | face-recognition | import a face to FAISS |

### Technologies

| Component | Technology |
|-----------|-----------|
| Container orchestration | Docker Compose |
| Message bus | Eclipse Mosquitto 2 (MQTT) |
| Face detection | InsightFace (SCRFD model) |
| Face embedding | ArcFace ResNet50 (512-dim vectors) |
| Vector search | FAISS (IndexFlatIP, cosine similarity) |
| Database | SQLite 3 (WAL mode) |
| Web dashboard | Flask + HTML/CSS/JS |
| Video capture | OpenCV (RTSP over TCP) |
| Notifications | Telegram Bot API |
| Language | Python 3.11 |

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Custom Firmware on the Intercom](#2-custom-firmware-on-the-intercom)
3. [SSH Access to the Intercom](#3-ssh-access-to-the-intercom)
4. [Installing c300x-controller](#4-installing-c300x-controller)
5. [MQTT Configuration on the Intercom](#5-mqtt-configuration-on-the-intercom)
6. [Server Setup (Mac/Linux)](#6-server-setup-maclinux)
7. [Docker Services Configuration](#7-docker-services-configuration)
8. [Registering Faces](#8-registering-faces)
9. [Auto-Unlock Configuration](#9-auto-unlock-configuration)
10. [Telegram Notifications](#10-telegram-notifications)
11. [Testing](#11-testing)
12. [Troubleshooting](#12-troubleshooting)

---

> Throughout this guide, `$INTERCOM_IP` and `$SERVER_IP` refer to the intercom and server IP addresses on the LAN, respectively. These are configured once in the `.env` file. To run commands directly, either replace the variables with your own IPs or export them in the terminal:
> ```
> export INTERCOM_IP=192.168.1.14
> export SERVER_IP=192.168.1.91
> ```

## 1. Prerequisites

### Hardware

- BTicino Classe 300X (model 344642 / C300X13E) or C100X
- Mini-USB cable (for firmware flashing)
- Windows PC (for MyHomeSuite)
- Always-on server on the same LAN (Mac, Linux, Raspberry Pi, NAS)

### Software

- Python 3 (or Docker) to generate the firmware
- MyHomeSuite (downloadable from the Legrand website)
- Docker and Docker Compose on the server
- SSH client

### Firmware Requirements

> **Only firmware v1.x is supported.** Versions v2.x use the Netatmo cloud and do not allow root access.

To check the version, look at the label on the back of the device or in the BTicino app.

---

## 2. Custom Firmware on the Intercom

### 2.1 Generate the Firmware

```bash
git clone https://github.com/fquinto/bticinoClasse300x.git
cd bticinoClasse300x

# With Python
sudo python3 main.py

# Or with Docker
docker compose run bticino
```

The script generates a modified `.fwz` firmware file with SSH enabled.

### 2.2 Flash the Firmware

1. Download and install **MyHomeSuite** from the Legrand website
2. Remove the intercom from the wall (keep the 2-wire SCS bus connected)
3. Connect the Mini-USB cable from the rear port of the device to the PC
4. Open MyHomeSuite and select the device model
5. Upload the generated `.fwz` firmware
6. Wait for flashing to complete and the device to reboot

> The device reboots automatically. The process takes about 5-10 minutes.

---

## 3. SSH Access to the Intercom

After flashing the custom firmware:

```bash
ssh -o HostKeyAlgorithms=+ssh-rsa root2@$INTERCOM_IP
```

- **User:** `root2`
- **Password:** `pwned123`

The `-o HostKeyAlgorithms=+ssh-rsa` flag is required because the device uses a legacy SSH algorithm.

### Verify Access

```bash
# Once connected
uname -a      # Should show armv7l
cat /etc/os-release
```

> To find the intercom's IP, check your router or use `nmap -sn 192.168.1.0/24`.

---

## 4. Installing c300x-controller

c300x-controller is the Node.js application that runs directly on the intercom. It exposes:
- **RTSP stream** on port 6554
- **HTTP API** on port 8080 (door/gate unlock)
- **MQTT events** on the `bticino/doorbell` topic

### 4.1 Automatic Installation

```bash
# Via SSH on the intercom
bash -c "$(wget -qO - 'https://raw.githubusercontent.com/slyoldfox/c300x-controller/main/install.sh')"
```

The script:
- Installs Node.js v17.9.1
- Downloads c300x-controller
- Configures the service for automatic startup
- Opens port 8080 in the firewall

### 4.2 Lock Configuration

The configuration file is `/home/bticino/cfg/extra/c300x-controller/config.json`:

```json
{
  "doorUnlock": {
    "openSequence": "*8*19*20##",
    "closeSequence": "*8*20*20##"
  }
}
```

The default OpenWebNet sequences work for the main lock. To add a secondary gate:

```json
{
  "doorUnlock": {
    "openSequence": "*8*19*20##",
    "closeSequence": "*8*20*20##"
  },
  "additionalLocks": {
    "gate": {
      "openSequence": "*8*19*21##",
      "closeSequence": "*8*20*21##"
    }
  }
}
```

### 4.3 Verify It Works

```bash
# From a PC on the same network

# Test the unlock API (shows the list of locks)
curl http://$INTERCOM_IP:8080/unlock

# Test the RTSP stream
ffplay -f rtsp -i rtsp://$INTERCOM_IP:6554/doorbell-video
```

### Ports Used by the Intercom

| Port | Service |
|------|---------|
| 22 | SSH |
| 5060 | SIP (flexisip) |
| 6554 | RTSP (c300x-controller) |
| 8080 | HTTP API (c300x-controller) |
| 20000 | OpenWebNet |

---

## 5. MQTT Configuration on the Intercom

c300x-controller publishes doorbell events via MQTT. It must point to the Mosquitto broker running on the server.

### 5.1 Configure c300x-controller

The configuration file is `/home/bticino/cfg/extra/c300x-controller/config.json`:

```bash
# Via SSH on the intercom
ssh -o HostKeyAlgorithms=+ssh-rsa root2@$INTERCOM_IP
vi /home/bticino/cfg/extra/c300x-controller/config.json
```

Set the `mqtt_config` section with the server IP:

```json
{
  "sip": {
    "from": "webrtc@127.0.0.1",
    "to": "c100x@$INTERCOM_IP",
    "domain": "<your-domain>.bs.iotleg.com",
    "debug": false
  },
  "mqtt_config": {
    "enabled": true,
    "all_events_enabled": true,
    "host": "$SERVER_IP",
    "port": 1883,
    "topic": "bticino"
  }
}
```

- **`host`**: the server IP where Docker/Mosquitto is running (`$SERVER_IP`)
- **`port`**: MQTT broker port (1883)
- **`topic`**: MQTT topic prefix (default: `bticino`)
- **`enabled`**: must be `true`

After editing, restart c300x-controller:

```bash
kill $(pgrep -f bundle.js)
# c300x-controller restarts automatically
```

### 5.2 Verify the MQTT Connection

From the server, listen for events:

```bash
docker compose exec mosquitto mosquitto_sub -t "bticino/#" -v
```

Press the doorbell. You should see:

```
bticino/doorbell pressed
```

> This is the event that the `doorbell-worker` service listens for to start frame capture.

---

## 6. Server Setup (Mac/Linux)

### 6.1 Clone the Repository

```bash
git clone <repository-url> face-recognition
cd face-recognition
```

### 6.2 Create the .env File

```bash
cat > .env << 'EOF'
INTERCOM_IP=192.168.1.14
SERVER_IP=192.168.1.91
TELEGRAM_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id
EOF
```

`INTERCOM_IP` is the intercom's IP address on the LAN. It is automatically used in `docker-compose.yml` for RTSP and the unlock API.

To get the Telegram token:
1. Contact @BotFather on Telegram
2. Create a new bot with `/newbot`
3. Copy the token

To get the chat_id:
1. Send a message to the newly created bot
2. Visit `https://api.telegram.org/botTOKEN/getUpdates`
3. Look for the `chat.id` field in the response

### 6.3 Configure the Intercom IP

The intercom IP is configured in the `.env` file via `INTERCOM_IP`. The `docker-compose.yml` uses it automatically:

```yaml
doorbell-worker:
  environment:
    - RTSP_URL=rtsp://${INTERCOM_IP}:6554/doorbell-video

gate-opener:
  environment:
    - UNLOCK_URL=http://${INTERCOM_IP}:8080/unlock?id=default
```

To change the IP, just edit `.env` — no need to modify `docker-compose.yml`.

### 6.4 Start All Services

```bash
docker compose up -d --build
```

The first startup downloads InsightFace models (~300MB). Verify:

```bash
docker compose ps          # All containers should be "Up"
docker compose logs -f     # Follow logs in real time
```

### 6.5 Firewall

The server must accept incoming connections on port 1883 (MQTT) from the intercom.

**macOS:**
- System Preferences > Security > Firewall > allow incoming connections
- Or add an exception for Docker/mosquitto

**Linux:**
```bash
sudo ufw allow 1883/tcp
```

---

## 7. Docker Services Configuration

### Architecture

```
Doorbell pressed
    │
    ▼
c300x-controller (intercom)
    │  publishes "bticino/doorbell: pressed"
    ▼
[mosquitto] ◀── central MQTT broker
    │
    ▼
doorbell-worker
    │  captures 4 frames via RTSP
    │  publishes to faceid/requests
    ▼
face-recognition
    │  runs detect + match on each frame
    │  publishes to faceid/results
    ▼
aggregator
    │  votes on results (min 2 matches = decision)
    │  publishes to doorbell/aggregated
    │
    ├───────┬───────┐
    │       │       │
    ▼       ▼       ▼
notifier  gate-   face-
(Telegram) opener  collector
          (unlock) (saves to DB)
```

### Services and Key Parameters

| Service | Port | Key Parameters |
|---------|------|---------------|
| mosquitto | 1883 | MQTT broker |
| face-recognition | - | MATCH_THRESHOLD=0.45 |
| aggregator | - | MIN_VOTES=2, FRAMES_EXPECTED=4, TIMEOUT=15s |
| notifier | - | TELEGRAM_TOKEN, TELEGRAM_CHAT_ID |
| doorbell-worker | - | RTSP_URL, FRAMES_TO_SAVE=4, INTERVAL=1.0s |
| gate-opener | - | UNLOCK_URL, MIN_CONFIDENCE=0.50 |
| doorbell-trigger | 5001 | Manual trigger via HTTP |
| face-collector | - | COOLDOWN=2.5s, MAX_FRAMES=4 |
| dashboard | 5050 | Web interface |

### Data Volumes

| Volume | Container Path | Contents |
|--------|---------------|----------|
| frames_data | /shared_frames | Captured frames, faces.db |
| ./services/data | /app/data | FAISS index, metadata.db |
| insightface_models | /root/.insightface | AI models (~300MB) |

---

## 8. Registering Faces

### 8.1 Automatic Collection

Every time the system detects a face (from the doorbell or continuous surveillance), the frame is saved to the database with `pending` status.

### 8.2 Web Dashboard

Access the dashboard at: `http://$SERVER_IP:5050`

The dashboard shows all captured faces. To register a person:

1. **Filter** faces with "Pending" status
2. **Select** the frames containing the person's face
3. **Assign the name** using the "Assign Name" field
4. **Import** by clicking "Import" to add the faces to the FAISS index

The system needs at least 3-5 photos per person from different angles for reliable recognition.

### 8.3 Import from File (CLI)

To import faces from existing photos (inside the container):

```bash
docker compose exec face-recognition python -m faceid import /path/photo.jpg --name "Person Name"
```

### 8.4 Quality Parameters

The system automatically discards low-quality frames:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| MIN_DET_SCORE | 0.50 | Minimum detection score |
| MIN_FACE_AREA_RATIO | 0.02 | Minimum face area in the frame |
| MIN_EYE_DISTANCE_PX | 20px | Minimum distance between eyes |
| MIN_EYE_SYMMETRY | 0.65 | Minimum eye symmetry |

---

## 9. Auto-Unlock Configuration

### 9.1 From the Dashboard

1. Open `http://$SERVER_IP:5050`
2. In the sidebar, find the "Auto-Open" section
3. Toggle the switch for people who should trigger automatic unlock

### 9.2 Unlock Flow

1. Doorbell pressed
2. System recognizes the person (confidence >= 50%)
3. Checks if `auto_open = true` in the `persons` table
4. If yes: calls `http://$INTERCOM_IP:8080/unlock?id=default`
5. Total time: ~6-7 seconds from ring to unlock

### 9.3 Security Threshold

The confidence threshold for automatic unlock is configurable:

```yaml
# docker-compose.yml
gate-opener:
  environment:
    - MIN_CONFIDENCE=0.50   # 50% - increase for higher security
```

---

## 10. Telegram Notifications

### 10.1 Create the Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name and username for the bot
4. Copy the token (format: `1234567890:AAEF-xxxxxxxxxxxxxxxxxxxxxxxxxxx`)

### 10.2 Get the chat_id

1. Send any message to the bot
2. Open in browser: `https://api.telegram.org/botTOKEN/getUpdates`
3. Look for `"chat":{"id":XXXXXXX}` in the JSON response

### 10.3 Configure .env

```bash
# .env file in the project root
TELEGRAM_TOKEN=1234567890:AAEF-xxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=624659241
```

### 10.4 What You Receive on Telegram

For each doorbell ring:
- Recognized person: photo + name + confidence percentage
- Unknown person: photo + "Unknown person" alert

---

## 11. Testing

### 11.1 Verify Services

```bash
# Container status
docker compose ps

# All service logs
docker compose logs -f

# Specific service log
docker compose logs -f doorbell-worker
```

### 11.2 Manual Doorbell Test

```bash
# Simulate a ring without pressing the physical doorbell
curl -X POST http://localhost:5001/ring
```

### 11.3 Verify MQTT Connection from the Intercom

```bash
# From the server, subscribe to the doorbell topic
docker compose exec mosquitto mosquitto_sub -t "bticino/doorbell" -v
```

Then press the physical doorbell. You should see: `bticino/doorbell pressed`

### 11.4 Verify the RTSP Stream

```bash
ffplay -f rtsp -rtsp_transport tcp -i rtsp://$INTERCOM_IP:6554/doorbell-video
```

### 11.5 Verify the Unlock API

```bash
# List available locks
curl http://$INTERCOM_IP:8080/unlock

# Unlock the door
curl http://$INTERCOM_IP:8080/unlock?id=default
```

### 11.6 Full End-to-End Test

1. Make sure all containers are "Up"
2. Press the physical doorbell
3. Check the logs: `docker compose logs -f --tail=0`
4. Verify the Telegram notification
5. If the person has auto_open enabled, verify that the gate opens

---

## 12. Troubleshooting

### doorbell-worker does not react to ring

```bash
# Check MQTT connection
docker compose logs doorbell-worker | grep -i "mqtt"

# Restart the service
docker compose restart doorbell-worker
```

### No faces detected in frames

- The camera is backlit or in shadow
- Try lowering MIN_DET_SCORE in `services/faceid/config.py`
- Check captured frames in the `frames_data` volume

### MQTT from the intercom does not reach the server

```bash
# From the intercom, test connectivity
ssh -o HostKeyAlgorithms=+ssh-rsa root2@$INTERCOM_IP
mosquitto_pub -h $SERVER_IP -p 1883 -t test -m "hello"
```

If it doesn't work: check the server firewall (port 1883).

### Gate does not open

```bash
# Check that gate-opener sees the person with auto_open
docker compose logs gate-opener

# Test the API manually
curl http://$INTERCOM_IP:8080/unlock?id=default

# Check registered persons
docker compose exec gate-opener python -c "
import sqlite3
conn = sqlite3.connect('/shared_frames/faces.db')
for r in conn.execute('SELECT name, auto_open FROM persons'):
    print(r)
conn.close()
"
```

### InsightFace models fail to download

```bash
# Remove the volume and recreate
docker compose down
docker volume rm face-recognition-main_insightface_models
docker compose up -d --build face-recognition
```

### SSH host key changed after reboot

```bash
ssh-keygen -R $INTERCOM_IP
ssh -o HostKeyAlgorithms=+ssh-rsa root2@$INTERCOM_IP
```

### Dashboard does not load

```bash
# Check that the frontend was built
docker compose logs dashboard | head -20

# Rebuild
docker compose up -d --build dashboard
```
