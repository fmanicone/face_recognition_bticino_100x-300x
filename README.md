# Guida completa: Face Recognition su BTicino Classe 300X

## Indice

1. [Prerequisiti](#1-prerequisiti)
2. [Firmware custom sul videocitofono](#2-firmware-custom-sul-videocitofono)
3. [Accesso SSH al videocitofono](#3-accesso-ssh-al-videocitofono)
4. [Installazione c300x-controller](#4-installazione-c300x-controller)
5. [Configurazione MQTT sul videocitofono](#5-configurazione-mqtt-sul-videocitofono)
6. [Setup del server (Mac/Linux)](#6-setup-del-server-maclinux)
7. [Configurazione dei servizi Docker](#7-configurazione-dei-servizi-docker)
8. [Registrazione volti nel sistema](#8-registrazione-volti-nel-sistema)
9. [Configurazione apertura automatica](#9-configurazione-apertura-automatica)
10. [Configurazione notifiche Telegram](#10-configurazione-notifiche-telegram)
11. [Verifica e test](#11-verifica-e-test)
12. [Troubleshooting](#12-troubleshooting)

---

> In tutta la guida `$INTERCOM_IP` e `$SERVER_IP` indicano rispettivamente l'IP del videocitofono e del server sulla LAN. I valori si configurano una sola volta nel file `.env`. Per eseguire i comandi, sostituire le variabili con i propri IP oppure esportarli nel terminale:
> ```
> export INTERCOM_IP=192.168.1.14
> export SERVER_IP=192.168.1.91
> ```

## 1. Prerequisiti

### Hardware

- BTicino Classe 300X (modello 344642 / C300X13E) o C100X
- Cavo Mini-USB (per il flash del firmware)
- PC Windows (per MyHomeSuite)
- Server sempre acceso sulla stessa LAN (Mac, Linux, Raspberry Pi, NAS)

### Software

- Python 3 (o Docker) per generare il firmware
- MyHomeSuite (scaricabile dal sito Legrand)
- Docker e Docker Compose sul server
- Client SSH

### Requisiti firmware

> **Solo firmware v1.x e' supportato.** Le versioni v2.x usano Netatmo cloud e non permettono il root.

Per verificare la versione, controlla l'etichetta sul retro del dispositivo o nell'app BTicino.

---

## 2. Firmware custom sul videocitofono

### 2.1 Generare il firmware

```bash
git clone https://github.com/fquinto/bticinoClasse300x.git
cd bticinoClasse300x

# Con Python
sudo python3 main.py

# Oppure con Docker
docker compose run bticino
```

Lo script genera un file firmware `.fwz` modificato con SSH abilitato.

### 2.2 Flash del firmware

1. Scaricare e installare **MyHomeSuite** dal sito Legrand
2. Smontare il videocitofono dalla parete (lasciare collegato il bus SCS a 2 fili)
3. Collegare il cavo Mini-USB dalla porta posteriore del dispositivo al PC
4. Aprire MyHomeSuite, selezionare il modello del dispositivo
5. Caricare il firmware `.fwz` generato
6. Attendere il completamento del flash e il riavvio del dispositivo

> Il dispositivo si riavvia automaticamente. Il processo richiede circa 5-10 minuti.

---

## 3. Accesso SSH al videocitofono

Dopo il flash del firmware custom:

```bash
ssh -o HostKeyAlgorithms=+ssh-rsa root2@$INTERCOM_IP
```

- **Utente:** `root2`
- **Password:** `pwned123`

Il flag `-o HostKeyAlgorithms=+ssh-rsa` e' necessario perche' il dispositivo usa un algoritmo SSH datato.

### Verificare l'accesso

```bash
# Una volta connesso
uname -a      # Deve mostrare armv7l
cat /etc/os-release
```

> Per trovare l'IP del videocitofono, controllare il router o usare `nmap -sn 192.168.1.0/24`.

---

## 4. Installazione c300x-controller

c300x-controller e' l'applicazione Node.js che gira direttamente sul videocitofono. Espone:
- **Stream RTSP** sulla porta 6554
- **API HTTP** sulla porta 8080 (apertura cancello/serratura)
- **Eventi MQTT** sul topic `bticino/doorbell`

### 4.1 Installazione automatica

```bash
# Da SSH sul videocitofono
bash -c "$(wget -qO - 'https://raw.githubusercontent.com/slyoldfox/c300x-controller/main/install.sh')"
```

Lo script:
- Installa Node.js v17.9.1
- Scarica c300x-controller
- Configura il servizio per l'avvio automatico
- Apre la porta 8080 nel firewall

### 4.2 Configurazione serrature

Il file di configurazione e' `/home/bticino/cfg/extra/c300x-controller/config.json`:

```json
{
  "doorUnlock": {
    "openSequence": "*8*19*20##",
    "closeSequence": "*8*20*20##"
  }
}
```

Le sequenze OpenWebNet di default funzionano per la serratura principale. Per aggiungere un cancello secondario:

```json
{
  "doorUnlock": {
    "openSequence": "*8*19*20##",
    "closeSequence": "*8*20*20##"
  },
  "additionalLocks": {
    "cancello": {
      "openSequence": "*8*19*21##",
      "closeSequence": "*8*20*21##"
    }
  }
}
```

### 4.3 Verificare che funzioni

```bash
# Da un PC sulla stessa rete

# Testare l'API unlock (mostra la lista serrature)
curl http://$INTERCOM_IP:8080/unlock

# Testare lo stream RTSP
ffplay -f rtsp -i rtsp://$INTERCOM_IP:6554/doorbell-video
```

### Porte usate dal videocitofono

| Porta | Servizio |
|-------|----------|
| 22 | SSH |
| 5060 | SIP (flexisip) |
| 6554 | RTSP (c300x-controller) |
| 8080 | HTTP API (c300x-controller) |
| 20000 | OpenWebNet |

---

## 5. Configurazione MQTT sul videocitofono

c300x-controller pubblica gli eventi del campanello su MQTT. Deve puntare al broker Mosquitto che gira sul server.

### 5.1 Configurare c300x-controller

Il file di configurazione e' `/home/bticino/cfg/extra/c300x-controller/config.json`:

```bash
# Da SSH sul videocitofono
ssh -o HostKeyAlgorithms=+ssh-rsa root2@$INTERCOM_IP
vi /home/bticino/cfg/extra/c300x-controller/config.json
```

Impostare la sezione `mqtt_config` con l'IP del server:

```json
{
  "sip": {
    "from": "webrtc@127.0.0.1",
    "to": "c100x@$INTERCOM_IP",
    "domain": "<il-tuo-domain>.bs.iotleg.com",
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

- **`host`**: l'IP del server dove gira Docker/Mosquitto (`$SERVER_IP`)
- **`port`**: porta del broker MQTT (1883)
- **`topic`**: prefisso dei topic MQTT (default: `bticino`)
- **`enabled`**: deve essere `true`

Dopo la modifica, riavviare c300x-controller:

```bash
kill $(pgrep -f bundle.js)
# c300x-controller si riavvia automaticamente
```

### 5.2 Verificare la connessione MQTT

Dal server, ascoltare gli eventi:

```bash
docker compose exec mosquitto mosquitto_sub -t "bticino/#" -v
```

Premere il campanello. Deve apparire:

```
bticino/doorbell pressed
```

> Questo e' l'evento che il servizio `doorbell-worker` ascolta per avviare la cattura dei frame.

---

## 6. Setup del server (Mac/Linux)

### 6.1 Clonare il repository

```bash
git clone <repository-url> face-recognition
cd face-recognition
```

### 6.2 Creare il file .env

```bash
cat > .env << 'EOF'
INTERCOM_IP=192.168.1.14
SERVER_IP=192.168.1.91
TELEGRAM_TOKEN=il_tuo_token_telegram
TELEGRAM_CHAT_ID=il_tuo_chat_id
EOF
```

`INTERCOM_IP` e' l'IP del videocitofono sulla LAN. Viene usato automaticamente in `docker-compose.yml` per RTSP e unlock API.

Per ottenere il token Telegram:
1. Contattare @BotFather su Telegram
2. Creare un nuovo bot con `/newbot`
3. Copiare il token

Per ottenere il chat_id:
1. Inviare un messaggio al bot appena creato
2. Visitare `https://api.telegram.org/botTOKEN/getUpdates`
3. Cercare il campo `chat.id` nella risposta

### 6.3 Configurare l'IP del videocitofono

L'IP del videocitofono si configura nel file `.env` tramite `INTERCOM_IP`. Il `docker-compose.yml` lo usa automaticamente:

```yaml
doorbell-worker:
  environment:
    - RTSP_URL=rtsp://${INTERCOM_IP}:6554/doorbell-video

gate-opener:
  environment:
    - UNLOCK_URL=http://${INTERCOM_IP}:8080/unlock?id=default
```

Per cambiare IP basta modificare `.env`, senza toccare `docker-compose.yml`.

### 6.4 Avviare tutti i servizi

```bash
docker compose up -d --build
```

Il primo avvio scarica i modelli InsightFace (~300MB). Verificare:

```bash
docker compose ps          # Tutti i container devono essere "Up"
docker compose logs -f     # Seguire i log in tempo reale
```

### 6.5 Firewall

Il server deve accettare connessioni in ingresso sulla porta 1883 (MQTT) dal videocitofono.

**macOS:**
- Preferenze di Sistema > Sicurezza > Firewall > consenti connessioni in ingresso
- Oppure aggiungere eccezione per Docker/mosquitto

**Linux:**
```bash
sudo ufw allow 1883/tcp
```

---

## 7. Configurazione dei servizi Docker

### Architettura

```
Campanello premuto
    |
    v
c300x-controller (videocitofono)
    |  pubblica "bticino/doorbell: pressed"
    v
[mosquitto] <-- broker MQTT centrale
    |
    v
doorbell-worker
    |  cattura 4 frame via RTSP
    |  pubblica su faceid/requests
    v
face-recognition
    |  esegue detect + match per ogni frame
    |  pubblica su faceid/results
    v
aggregator
    |  vota i risultati (min 2 match = decisione)
    |  pubblica su doorbell/aggregated
    |
    +-------+-------+
    |               |
    v               v
notifier        gate-opener
(Telegram)      (apre cancello)
```

### Servizi e parametri principali

| Servizio | Porta | Parametri chiave |
|----------|-------|-----------------|
| mosquitto | 1883 | Broker MQTT |
| face-recognition | - | MATCH_THRESHOLD=0.45 |
| aggregator | - | MIN_VOTES=2, FRAMES_EXPECTED=4, TIMEOUT=15s |
| notifier | - | TELEGRAM_TOKEN, TELEGRAM_CHAT_ID |
| doorbell-worker | - | RTSP_URL, FRAMES_TO_SAVE=4, INTERVAL=1.0s |
| gate-opener | - | UNLOCK_URL, MIN_CONFIDENCE=0.50 |
| doorbell-trigger | 5001 | Trigger manuale via HTTP |
| face-collector | - | COOLDOWN=2.5s, MAX_FRAMES=4 |
| dashboard | 5050 | Interfaccia web |

### Volumi dati

| Volume | Path nel container | Contenuto |
|--------|-------------------|-----------|
| frames_data | /shared_frames | Frame catturati, faces.db |
| ./services/data | /app/data | Indice FAISS, metadata.db |
| insightface_models | /root/.insightface | Modelli AI (~300MB) |

---

## 8. Registrazione volti nel sistema

### 8.1 Raccolta automatica

Ogni volta che il sistema rileva un volto (dal campanello o dalla sorveglianza continua), il frame viene salvato nel database con stato `pending`.

### 8.2 Dashboard web

Accedere alla dashboard: `http://$SERVER_IP:5050`

La dashboard mostra tutti i volti catturati. Per registrare una persona:

1. **Filtrare** i volti con stato "Pending"
2. **Selezionare** i frame che contengono il volto della persona
3. **Assegnare il nome** usando il campo "Assign Name"
4. **Importare** cliccando "Import" per aggiungere i volti all'indice FAISS

Il sistema necessita di almeno 3-5 foto per persona da angolazioni diverse per un riconoscimento affidabile.

### 8.3 Import da file (CLI)

Per importare volti da foto esistenti (dentro il container):

```bash
docker compose exec face-recognition python -m faceid import /path/foto.jpg --name "Nome Persona"
```

### 8.4 Parametri di qualita'

Il sistema scarta automaticamente i frame di bassa qualita':

| Parametro | Valore | Significato |
|-----------|--------|-------------|
| MIN_DET_SCORE | 0.50 | Score minimo di detection |
| MIN_FACE_AREA_RATIO | 0.02 | Area minima del volto nel frame |
| MIN_EYE_DISTANCE_PX | 20px | Distanza minima tra gli occhi |
| MIN_EYE_SYMMETRY | 0.65 | Simmetria minima degli occhi |

---

## 9. Configurazione apertura automatica

### 9.1 Dalla dashboard

1. Aprire `http://$SERVER_IP:5050`
2. Nel pannello laterale, sezione "Auto-Open"
3. Attivare lo switch per le persone che devono aprire automaticamente

### 9.2 Flusso di apertura

1. Campanello premuto
2. Sistema riconosce la persona (confidence >= 50%)
3. Controlla se `auto_open = true` nella tabella `persons`
4. Se si': chiama `http://$INTERCOM_IP:8080/unlock?id=default`
5. Tempo totale: ~6-7 secondi dal ring all'apertura

### 9.3 Soglia di sicurezza

La soglia di confidenza per l'apertura automatica e' configurabile:

```yaml
# docker-compose.yml
gate-opener:
  environment:
    - MIN_CONFIDENCE=0.50   # 50% - aumentare per maggiore sicurezza
```

---

## 10. Configurazione notifiche Telegram

### 10.1 Creare il bot

1. Aprire Telegram e cercare **@BotFather**
2. Inviare `/newbot`
3. Scegliere un nome e username per il bot
4. Copiare il token (formato: `1234567890:AAEF-xxxxxxxxxxxxxxxxxxxxxxxxxxx`)

### 10.2 Ottenere il chat_id

1. Inviare un messaggio qualsiasi al bot
2. Aprire nel browser: `https://api.telegram.org/botTOKEN/getUpdates`
3. Cercare `"chat":{"id":XXXXXXX}` nella risposta JSON

### 10.3 Configurare il .env

```bash
# file .env nella root del progetto
TELEGRAM_TOKEN=1234567890:AAEF-xxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=624659241
```

### 10.4 Cosa ricevi su Telegram

Per ogni ring del campanello:
- Persona riconosciuta: foto + nome + percentuale di confidenza
- Persona sconosciuta: foto + avviso "Persona sconosciuta"

---

## 11. Verifica e test

### 11.1 Verificare i servizi

```bash
# Stato dei container
docker compose ps

# Log di tutti i servizi
docker compose logs -f

# Log di un servizio specifico
docker compose logs -f doorbell-worker
```

### 11.2 Test manuale del campanello

```bash
# Simulare un ring senza premere il campanello fisico
curl -X POST http://localhost:5001/ring
```

### 11.3 Verificare la connessione MQTT dal videocitofono

```bash
# Dal server, sottoscrivere il topic del campanello
docker compose exec mosquitto mosquitto_sub -t "bticino/doorbell" -v
```

Poi premere il campanello fisico. Deve apparire: `bticino/doorbell pressed`

### 11.4 Verificare lo stream RTSP

```bash
ffplay -f rtsp -rtsp_transport tcp -i rtsp://$INTERCOM_IP:6554/doorbell-video
```

### 11.5 Verificare l'API unlock

```bash
# Lista serrature disponibili
curl http://$INTERCOM_IP:8080/unlock

# Aprire la serratura
curl http://$INTERCOM_IP:8080/unlock?id=default
```

### 11.6 Test completo end-to-end

1. Assicurarsi che tutti i container siano "Up"
2. Premere il campanello fisico
3. Controllare i log: `docker compose logs -f --tail=0`
4. Verificare la notifica Telegram
5. Se la persona ha auto_open, verificare che il cancello si apra

---

## 12. Troubleshooting

### Il doorbell-worker non reagisce al ring

```bash
# Verificare la connessione MQTT
docker compose logs doorbell-worker | grep -i "mqtt"

# Riavviare il servizio
docker compose restart doorbell-worker
```

### Nessun volto rilevato nei frame

- La camera e' controluce o in ombra
- Provare ad abbassare MIN_DET_SCORE in `services/faceid/config.py`
- Verificare i frame catturati nel volume `frames_data`

### MQTT dal videocitofono non arriva al server

```bash
# Dal videocitofono, testare la connettivita'
ssh -o HostKeyAlgorithms=+ssh-rsa root2@$INTERCOM_IP
mosquitto_pub -h $SERVER_IP -p 1883 -t test -m "hello"
```

Se non funziona: verificare il firewall del server (porta 1883).

### Il cancello non si apre

```bash
# Verificare che gate-opener veda la persona con auto_open
docker compose logs gate-opener

# Testare l'API manualmente
curl http://$INTERCOM_IP:8080/unlock?id=default

# Verificare le persone registrate
docker compose exec gate-opener python -c "
import sqlite3
conn = sqlite3.connect('/shared_frames/faces.db')
for r in conn.execute('SELECT name, auto_open FROM persons'):
    print(r)
conn.close()
"
```

### I modelli InsightFace non si scaricano

```bash
# Rimuovere il volume e ricreare
docker compose down
docker volume rm face-recognition-main_insightface_models
docker compose up -d --build face-recognition
```

### SSH host key cambiata dopo riavvio

```bash
ssh-keygen -R $INTERCOM_IP
ssh -o HostKeyAlgorithms=+ssh-rsa root2@$INTERCOM_IP
```

### Dashboard non si carica

```bash
# Verificare che il frontend sia stato compilato
docker compose logs dashboard | head -20

# Ricostruire
docker compose up -d --build dashboard
```
