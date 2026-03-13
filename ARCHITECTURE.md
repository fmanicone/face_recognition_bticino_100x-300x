# Architettura del Sistema

Sistema distribuito di riconoscimento facciale per citofono smart, basato su MQTT come bus di comunicazione tra microservizi Python containerizzati con Docker.

---

## Diagramma generale

```mermaid
graph TD
    subgraph Hardware / Esterno
        CAM["📷 Telecamera RTSP\n192.168.1.4"]
        BELL["🔔 ESP32 Citofono\n(simulato da doorbell-trigger)"]
    end

    subgraph Docker Network
        MQ["🟢 mosquitto\nMQTT Broker :1883"]

        DT["doorbell-trigger\n:5001 (HTTP → MQTT)"]
        DW["doorbell-worker\nRTSP reader + ring buffer"]
        FC["face-collector\nSole DB owner\nSession manager"]
        FR["face-recognition\nInsightFace + FAISS"]
        AG["aggregator\nVote aggregator"]
        NT["notifier\nNotifica finale"]
        DB["dashboard\nFlask :5050"]
    end

    subgraph Volumi condivisi
        FD[("frames_data\n/shared_frames\n• *.jpg\n• faces.db")]
        DATA[("./services/data\n/app/data\n• index.faiss\n• metadata.jsonl")]
        IFM[("insightface_models\n/root/.insightface")]
    end

    BELL -->|HTTP POST /ring| DT
    DT -->|doorbell/events/ring| MQ
    CAM -->|RTSP| DW

    MQ -->|doorbell/events/ring| DW

    DW -->|camera/frames\n(path JPG ogni 2s)| MQ
    DW -->|faceid/requests\n(session_id + 4 paths)| MQ
    DW -->|scrive JPG| FD

    MQ -->|camera/frames| FC
    FC -->|legge/scrive faces.db| FD
    FC -->|faceid/collector/match-requests\n(record_id + path)| MQ

    MQ -->|faceid/requests| FR
    MQ -->|faceid/collector/match-requests| FR
    MQ -->|faceid/import-requests| FR
    MQ -->|faceid/db/update| FC
    MQ -->|faceid/db/delete| FC
    MQ -->|faceid/db/bulk-update| FC
    MQ -->|faceid/db/bulk-delete| FC

    FR -->|faceid/results\n(session_id + match)| MQ
    FR -->|faceid/collector/match-results\n(record_id + match)| MQ
    FR -->|faceid/import-results| MQ
    FR -->|faceid/db/update| MQ
    FR -->|faceid/db/delete| MQ
    FR -->|legge JPG| FD
    FR -->|legge/scrive FAISS| DATA
    FR -->|modelli| IFM

    MQ -->|faceid/results| AG
    AG -->|faceid/notification| MQ
    MQ -->|faceid/notification| NT

    MQ -->|faceid/collector/match-results| FC

    DB -->|legge faces.db + JPG| FD
    DB -->|faceid/import-requests| MQ
    DB -->|faceid/db/bulk-update| MQ
    DB -->|faceid/db/bulk-delete| MQ
```

---

## Servizi

### `mosquitto`
Broker MQTT Eclipse Mosquitto 2. È il bus centrale di comunicazione: tutti i servizi pubblicano e si sottoscrivono tramite esso. Esposto sulla porta `1883`.

---

### `doorbell-trigger`
Simula un citofono ESP32. Espone un endpoint HTTP (`POST /ring`) sulla porta `5001` che pubblica il topic `doorbell/events/ring` con il `device_id` configurato. In produzione verrebbe sostituito dall'hardware reale.

---

### `doorbell-worker`
Legge il flusso video dalla telecamera via RTSP e gestisce due flussi paralleli:

- **Flusso continuo** — pubblica ogni `COLLECTOR_INTERVAL_S` (default 2s) il path di un frame JPG sul topic `camera/frames`. Il frame viene salvato in `/shared_frames/collector/<timestamp>.jpg`.
- **Flusso eventi ring** — quando arriva `doorbell/events/ring`, estrae 4 frame dal ring buffer e li salva in `/shared_frames/<session_id>/frame_N.jpg`, poi pubblica il topic `faceid/requests` con il `session_id` e i relativi path.

Non accede al database e non esegue riconoscimento facciale.

---

### `face-collector`
**Unico writer del database SQLite.**

Raccoglie continuamente i frame pubblicati da `doorbell-worker` su `camera/frames`. Per ogni frame avvia una sessione di raccolta:
- chiede a `face-recognition` di eseguire un match sul frame (via `faceid/collector/match-requests`)
- riceve il risultato su `faceid/collector/match-results`
- salva il record nella tabella `detected_faces` se non è già noto (o se non supera la soglia di somiglianza)

Gestisce anche le richieste di modifica DB inoltrate dagli altri servizi tramite i topic:
- `faceid/db/update` — aggiorna un singolo record
- `faceid/db/delete` — elimina un singolo record (+ file)
- `faceid/db/bulk-update` — aggiornamento batch
- `faceid/db/bulk-delete` — eliminazione batch (+ file)

La logica DB è isolata nel modulo `db.py`.

---

### `face-recognition`
Esegue il riconoscimento facciale con **InsightFace** e **FAISS**.

Gestisce tre tipi di richiesta:
1. **Ring match** (`faceid/requests`) — confronta i 4 frame di un evento ring contro il FAISS index e pubblica il risultato su `faceid/results`.
2. **Collector match** (`faceid/collector/match-requests`) — confronta un singolo frame continuo e pubblica su `faceid/collector/match-results`.
3. **Import** (`faceid/import-requests`) — aggiunge un volto al FAISS index (`index.faiss` + `metadata.jsonl`). In caso di successo elimina il record dal DB via `faceid/db/delete`; in caso di errore riporta lo stato a `pending` via `faceid/db/update`.

**Non accede direttamente a SQLite**: tutte le modifiche al DB passano per i topic `faceid/db/*`.

---

### `aggregator`
Aggrega i risultati di riconoscimento per `session_id`. Ogni evento ring genera 4 frame, ognuno produce un risultato su `faceid/results`. L'aggregator raccoglie i voti per `SESSION_TIMEOUT_S` (default 15s) e determina il match finale con soglia di `MIN_VOTES` (default 2). Il risultato finale viene pubblicato su `faceid/notification`.

---

### `notifier`
Riceve la notifica finale da `faceid/notification` e la consegna all'utente (es. push notification, log, ecc.).

---

### `dashboard`
Interfaccia web Flask sulla porta `5050` per gestire i volti raccolti da `face-collector`.

Struttura interna:
| File | Ruolo |
|------|-------|
| `app.py` | Route Flask, logica HTTP |
| `db.py` | Query SQLite in **sola lettura** |
| `mqtt_publisher.py` | Pubblica su `faceid/import-requests`, `faceid/db/bulk-update`, `faceid/db/bulk-delete` |
| `templates/index.html` | UI dark theme, Jinja2 |
| `static/dashboard.css` | Stili (layout sidebar, card grid, lightbox) |
| `static/dashboard.js` | Logica frontend (selezione bulk, lightbox, toast, API calls) |

---

## Tabella topic MQTT

| Topic | Publisher | Subscriber | Payload |
|-------|-----------|------------|---------|
| `doorbell/events/ring` | doorbell-trigger | doorbell-worker | `{ device_id }` |
| `camera/frames` | doorbell-worker | face-collector | `{ path }` |
| `faceid/requests` | doorbell-worker | face-recognition | `{ session_id, paths[] }` |
| `faceid/results` | face-recognition | aggregator | `{ session_id, match, score }` |
| `faceid/collector/match-requests` | face-collector | face-recognition | `{ record_id, path }` |
| `faceid/collector/match-results` | face-recognition | face-collector | `{ record_id, match, score }` |
| `faceid/import-requests` | dashboard | face-recognition | `{ record_id, image_path, name }` |
| `faceid/import-results` | face-recognition | — (log) | `{ record_id, success, error? }` |
| `faceid/db/update` | face-recognition | face-collector | `{ record_id, fields }` |
| `faceid/db/delete` | face-recognition | face-collector | `{ record_id }` |
| `faceid/db/bulk-update` | dashboard | face-collector | `{ ids[], fields }` |
| `faceid/db/bulk-delete` | dashboard | face-collector | `{ ids[] }` |
| `faceid/notification` | aggregator | notifier | `{ session_id, name?, score? }` |

---

## Ownership del database

**Solo `face-collector` scrive su `faces.db`.** Tutti gli altri servizi che devono modificare il DB pubblicano un messaggio MQTT su `faceid/db/*` e `face-collector` esegue l'operazione.

Questo evita race condition da accesso concorrente e centralizza la logica di persistenza in un unico posto.

```
faces.db schema:
  detected_faces (
    id            INTEGER PRIMARY KEY,
    image_path    TEXT,
    detected_at   TEXT,
    session_id    TEXT,
    status        TEXT,          -- pending | importing | imported | discarded
    suggested_name  TEXT,
    suggested_score REAL,
    assigned_name TEXT
  )
```

---

## Flusso eventi principali

### 1. Evento ring (identificazione visitatore)

```
[Citofono] → doorbell/events/ring
  → doorbell-worker estrae 4 frame dal ring buffer
  → salva in /shared_frames/<session_id>/
  → pubblica faceid/requests
    → face-recognition: InsightFace + FAISS su ogni frame
    → pubblica faceid/results (per ogni frame)
      → aggregator: aggrega voti per session_id
      → pubblica faceid/notification
        → notifier: consegna notifica
```

### 2. Raccolta continua (training data)

```
[Telecamera RTSP] → doorbell-worker salva frame ogni 2s
  → pubblica camera/frames
    → face-collector: avvia sessione se cooldown scaduto
    → pubblica faceid/collector/match-requests
      → face-recognition: match frame vs FAISS index
      → pubblica faceid/collector/match-results
        → face-collector: se volto nuovo → insert in faces.db
```

### 3. Import nel dataset (dalla dashboard)

```
[Dashboard] POST /api/faces/bulk-import
  → mqtt_publisher: pubblica faceid/db/bulk-update (status=importing)
  → mqtt_publisher: pubblica faceid/import-requests
    → face-recognition: estrae embedding, aggiunge a FAISS + metadata.jsonl
    → on success: pubblica faceid/db/delete (rimuove record pending)
    → on failure: pubblica faceid/db/update (status=pending)
```

---

## Volumi Docker

| Volume | Montato in | Usato da |
|--------|------------|----------|
| `frames_data` | `/shared_frames` | doorbell-worker (write JPG), face-collector (write JPG + faces.db), face-recognition (read JPG), dashboard (read JPG + faces.db) |
| `./services/data` | `/app/data` | face-recognition (read/write FAISS index + metadata.jsonl) |
| `insightface_models` | `/root/.insightface` | face-recognition (cache modelli, evita re-download) |

---

## Stack tecnologico

| Componente | Tecnologia |
|------------|-----------|
| Container orchestration | Docker Compose |
| MQTT broker | Eclipse Mosquitto 2 |
| Python runtime | Python 3.11-slim |
| MQTT client | paho-mqtt 2.x (`CallbackAPIVersion.VERSION2`) |
| Face detection / embedding | InsightFace |
| Vector search | FAISS |
| Database | SQLite (WAL mode) |
| Web framework | Flask + Jinja2 |
| Video streaming | OpenCV + RTSP (`rtsp_transport=tcp`) |
