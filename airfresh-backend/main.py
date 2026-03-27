import json
import sqlite3
import threading
from datetime import datetime

import paho.mqtt.client as mqtt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

MQTT_HOST = "0fe9edc83a224fcaa9dc18d5f3fde874.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "freshener"
MQTT_PASS = "EsP-3232"
DB_PATH   = "airfresh.db"

# ── DB ────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT UNIQUE,
        name TEXT,
        registered_at TEXT,
        last_seen TEXT,
        online_status TEXT DEFAULT 'offline',
        current_interval INTEGER DEFAULT 15,
        total_sprays INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS spray_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        spray_count INTEGER,
        trigger_type TEXT,
        interval_at_time INTEGER,
        uptime TEXT,
        timestamp TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS interval_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        old_interval INTEGER,
        new_interval INTEGER,
        changed_at TEXT
    )''')
    conn.commit()
    conn.close()
    print("[DB] Ready")

# ── MQTT ──────────────────────────────────────────────────
mqtt_client = mqtt.Client(client_id="fastapi-backend")
latest_status = {}

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Connected")
        client.subscribe("airfreshener/+/spray")
        client.subscribe("airfreshener/+/status")
        client.subscribe("airfreshener/+/online")
        client.subscribe("airfreshener/+/interval_log")
    else:
        print(f"[MQTT] Failed rc={rc}")

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        data = json.loads(msg.payload.decode())
    except:
        return

    parts = topic.split("/")
    if len(parts) < 3:
        return

    device_id = parts[1]
    event     = parts[2]
    ts        = datetime.utcnow().isoformat()
    conn      = get_db()
    c         = conn.cursor()

    if event == "spray":
        c.execute(
            "INSERT INTO spray_logs (device_id, spray_count, trigger_type, interval_at_time, uptime, timestamp) VALUES (?,?,?,?,?,?)",
            (device_id, data.get("count", 0), data.get("trigger", "auto"),
             data.get("interval_at_time", 0), data.get("uptime", ""), ts)
        )
        c.execute(
            "UPDATE devices SET total_sprays = total_sprays + 1, last_seen = ? WHERE device_id = ?",
            (ts, device_id)
        )
        print(f"[SPRAY] {device_id} #{data.get('count')} ({data.get('trigger')})")

    elif event == "status":
        latest_status[device_id] = data
        c.execute(
            "UPDATE devices SET last_seen=?, online_status='online', current_interval=? WHERE device_id=?",
            (ts, data.get("interval", 15), device_id)
        )

    elif event == "online":
        c.execute(
            '''INSERT INTO devices (device_id, name, registered_at, last_seen, online_status, current_interval, total_sprays)
               VALUES (?,?,?,?,'online',15,0)
               ON CONFLICT(device_id) DO UPDATE SET
               name=excluded.name, last_seen=excluded.last_seen, online_status='online' ''',
            (device_id, data.get("device_name", device_id), ts, ts)
        )
        print(f"[ONLINE] {device_id} registered")

    elif event == "interval_log":
        c.execute(
            "INSERT INTO interval_logs (device_id, old_interval, new_interval, changed_at) VALUES (?,?,?,?)",
            (device_id, data.get("old_interval", 0), data.get("new_interval", 0), ts)
        )

    conn.commit()
    conn.close()

def start_mqtt():
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.tls_set()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_forever()

# ── FastAPI ───────────────────────────────────────────────
app = FastAPI()

app.add_middleware(CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup")
def startup():
    init_db()
    t = threading.Thread(target=start_mqtt, daemon=True)
    t.start()
    print("[APP] Started")

# ── API Routes ────────────────────────────────────────────
@app.get("/api/sprays")
def get_sprays():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM spray_logs ORDER BY id DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/devices")
def get_devices():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM devices ORDER BY last_seen DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/status/{device_id}")
def get_status(device_id: str):
    return latest_status.get(device_id, {"error": "no data yet"})

@app.get("/api/interval-logs")
def get_interval_logs():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM interval_logs ORDER BY id DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

class CommandPayload(BaseModel):
    device_id: str

class IntervalPayload(BaseModel):
    device_id: str
    interval: int

@app.post("/api/spray")
def send_spray(payload: CommandPayload):
    topic = f"airfreshener/{payload.device_id}/command"
    mqtt_client.publish(topic, "spray")
    return {"status": "sent", "topic": topic}

@app.post("/api/interval")
def send_interval(payload: IntervalPayload):
    val = max(3, min(120, payload.interval))
    topic = f"airfreshener/{payload.device_id}/interval"
    mqtt_client.publish(topic, str(val))
    return {"status": "sent", "interval": val}

# ── Serve frontend ────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")