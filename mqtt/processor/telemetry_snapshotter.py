import os
import json
import time
import paho.mqtt.client as mqtt
from datetime import datetime

BROKER = "localhost"
PORT = 1883

SNAPSHOT_INTERVAL = 15      # every 15 seconds
MAX_SNAPSHOTS = 500         # keep only last 500 snapshots

topic_cache = {}

#  Match your screenshot paths
OUTPUT_DIR = os.path.join("mqtt", "processor", "data", "snapshots")
EVENTS_DIR = os.path.join("mqtt", "processor", "data", "events")
EVENTS_FILE = os.path.join(EVENTS_DIR, "events.jsonl")

# Track last-seen values so we only log changes
last_seen = {
    "race_leader": None,        # tuple (leader_driver, leader_lap)
    "fastest": None,            # tuple (fastest_driver, fastest_speed)
    "driver_laps": {},          # key team/driver -> lap int
    "driver_accident": {},      # key team/driver -> accident int (0/1)
    "winners": set()            # set of (circuit, winner_driver) to avoid duplicates
}

def now_human():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def safe_int(x):
    try:
        return int(float(x))
    except Exception:
        return None

def enforce_snapshot_limit():
    """Keep only the latest MAX_SNAPSHOTS snapshot files."""
    if not os.path.isdir(OUTPUT_DIR):
        return

    files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")]
    files.sort()  # timestamp filenames sort correctly

    if len(files) > MAX_SNAPSHOTS:
        to_delete = files[:len(files) - MAX_SNAPSHOTS]
        for f in to_delete:
            try:
                os.remove(os.path.join(OUTPUT_DIR, f))
            except Exception as e:
                print(f" Could not delete {f}: {e}")

def log_event(event_type: str, payload: dict):
    """Append one event as a JSON line."""
    os.makedirs(EVENTS_DIR, exist_ok=True)
    record = {
        "timestamp": now_human(),
        "type": event_type,
        "data": payload
    }
    with open(EVENTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def on_connect(client, userdata, flags, rc):
    print(" Snapshotter connected to MQTT")
    client.subscribe("f1/#")
    client.subscribe("race/#")

def on_message(client, userdata, msg):
    topic_cache[msg.topic] = {
        "value": msg.payload.decode(),
        "timestamp": now_human()
    }

def build_snapshot():
    snapshot = {
        "snapshot_time": now_human(),
        "telemetry": {},
        "analytics": {}
    }

    for topic, record in topic_cache.items():
        parts = topic.split("/")

        if parts[0] == "f1" and len(parts) >= 4:
            team = parts[1]
            driver = parts[2]
            metric = parts[3]

            snapshot["telemetry"].setdefault(team, {})
            snapshot["telemetry"][team].setdefault(driver, {})
            snapshot["telemetry"][team][driver][metric] = record

        elif parts[0] == "race":
            metric = "/".join(parts[1:])
            snapshot["analytics"][metric] = record

    return snapshot

def detect_and_log_events(snapshot: dict):
    """Logs only when something changes (compact event history)."""
    analytics = snapshot.get("analytics", {})
    telemetry = snapshot.get("telemetry", {})

    # Leader changes
    leader_driver = analytics.get("leader_driver", {}).get("value")
    leader_lap = analytics.get("leader_lap", {}).get("value")
    leader_tuple = (leader_driver, leader_lap)

    if leader_driver and leader_tuple != last_seen["race_leader"]:
        log_event("RACE_LEADER_CHANGED", {"leader": leader_driver, "lap": leader_lap})
        last_seen["race_leader"] = leader_tuple

    # Fastest changes
    fastest_driver = analytics.get("fastest_driver", {}).get("value")
    fastest_speed = analytics.get("fastest_speed", {}).get("value")
    fastest_tuple = (fastest_driver, fastest_speed)

    if fastest_driver and fastest_tuple != last_seen["fastest"]:
        log_event("FASTEST_DRIVER_CHANGED", {"fastest_driver": fastest_driver, "fastest_speed": fastest_speed})
        last_seen["fastest"] = fastest_tuple

    # Per-driver lap changes + accident start + winner decided
    for team, drivers in telemetry.items():
        for driver, metrics in drivers.items():
            key = f"{team}/{driver}"

            circuit = metrics.get("circuit", {}).get("value")
            lap_val = safe_int(metrics.get("lap", {}).get("value"))
            race_laps = safe_int(metrics.get("race_laps", {}).get("value"))
            sector = metrics.get("sector", {}).get("value")

            # Lap change
            if lap_val is not None:
                prev_lap = last_seen["driver_laps"].get(key)
                if prev_lap is None:
                    last_seen["driver_laps"][key] = lap_val
                elif lap_val != prev_lap:
                    log_event("LAP_CHANGED", {"driver": key, "from": prev_lap, "to": lap_val, "circuit": circuit})
                    last_seen["driver_laps"][key] = lap_val

            # Accident start (0 -> 1)
            acc_val = safe_int(metrics.get("accident", {}).get("value"))
            if acc_val is not None:
                prev_acc = last_seen["driver_accident"].get(key, 0)
                if prev_acc == 0 and acc_val == 1:
                    log_event("ACCIDENT_DETECTED", {"driver": key, "circuit": circuit, "lap": lap_val, "sector": sector})
                last_seen["driver_accident"][key] = acc_val

            # Winner decided (only once per circuit/driver)
            if circuit and lap_val is not None and race_laps is not None:
                if lap_val >= race_laps:
                    winner_key = (circuit, key)
                    if winner_key not in last_seen["winners"]:
                        log_event("WINNER_DECIDED", {"circuit": circuit, "winner": key, "race_laps": race_laps})
                        last_seen["winners"].add(winner_key)

def save_snapshot(snapshot):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    #  millisecond filename (prevents overwrite)
    filename = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    print(f" Snapshot saved: {filename}")

    enforce_snapshot_limit()

def main():
    client = mqtt.Client()
    client.reconnect_delay_set(min_delay=1, max_delay=5)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT, 60)
    client.loop_start()

    time.sleep(2)  # warm up cache

    while True:
        snapshot = build_snapshot()
        detect_and_log_events(snapshot)
        save_snapshot(snapshot)
        time.sleep(SNAPSHOT_INTERVAL)

if __name__ == "__main__":
    main()