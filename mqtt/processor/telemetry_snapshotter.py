import os
import json
import time
import paho.mqtt.client as mqtt
from datetime import datetime
from mqtt.adapters.loader import get_adapter
from mqtt.config import DATASET_ADAPTER

adapter = get_adapter()

BROKER = "localhost"
PORT = 1883

SNAPSHOT_INTERVAL = 15
MAX_SNAPSHOTS = 500

topic_cache = {}

BASE_OUTPUT_DIR = os.path.join("mqtt", "processor", "data", DATASET_ADAPTER)
OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, "snapshots")
EVENTS_DIR = os.path.join(BASE_OUTPUT_DIR, "events")
EVENTS_FILE = os.path.join(EVENTS_DIR, "events.jsonl")

last_seen = adapter.init_last_seen()


def now_human():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def enforce_snapshot_limit():
    if not os.path.isdir(OUTPUT_DIR):
        return

    files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")]
    files.sort()

    if len(files) > MAX_SNAPSHOTS:
        to_delete = files[:len(files) - MAX_SNAPSHOTS]
        for f in to_delete:
            try:
                os.remove(os.path.join(OUTPUT_DIR, f))
            except Exception as e:
                print(f"⚠️ Could not delete {f}: {e}")


def log_event(event_type: str, payload: dict):
    os.makedirs(EVENTS_DIR, exist_ok=True)

    record = {
        "timestamp": now_human(),
        "type": event_type,
        "data": payload
    }

    with open(EVENTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def on_connect(client, userdata, flags, rc):
    print(f"Snapshotter connected to MQTT | Dataset: {DATASET_ADAPTER}")
    for topic in adapter.INPUT_TOPICS_SNAPSHOTTER:
        client.subscribe(topic)


def on_message(client, userdata, msg):
    topic_cache[msg.topic] = {
        "value": msg.payload.decode(),
        "timestamp": now_human()
    }


def save_snapshot(snapshot):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    filename = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    print(f" Snapshot saved: {filepath}")
    enforce_snapshot_limit()


def main():
    client = mqtt.Client()
    client.reconnect_delay_set(min_delay=1, max_delay=5)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT, 60)
    client.loop_start()

    time.sleep(2)

    while True:
        snapshot = adapter.build_snapshot_from_cache(topic_cache, now_human())
        adapter.detect_events(snapshot, last_seen, log_event)
        save_snapshot(snapshot)
        time.sleep(SNAPSHOT_INTERVAL)


if __name__ == "__main__":
    main()