import os
import json
import glob

# =========================================
# CONFIG (Do NOT change)
# =========================================

# Snapshot + Event paths (must match snapshotter)
SNAPSHOT_DIR = os.path.join("mqtt", "processor", "data", "snapshots")
EVENT_LOG_FILE = os.path.join("mqtt", "processor", "data", "events", "events.jsonl")

# Output chunk folders
CHUNKS_DIR = os.path.join("data", "chunks")
SNAPSHOT_CHUNKS_DIR = os.path.join(CHUNKS_DIR, "snapshots")
EVENT_CHUNKS_DIR = os.path.join(CHUNKS_DIR, "events")

SNAPSHOTS_PER_CHUNK = 20
EVENTS_PER_CHUNK = 200


# =========================================
# HELPERS
# =========================================

def ensure_dirs():
    os.makedirs(SNAPSHOT_CHUNKS_DIR, exist_ok=True)
    os.makedirs(EVENT_CHUNKS_DIR, exist_ok=True)


def safe_read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f" Failed to read JSON: {path} | {e}")
        return None


# =========================================
# IMPROVED NATURAL LANGUAGE FORMATTER
# =========================================

def format_snapshot_to_text(snapshot: dict) -> str:
    lines = []

    snap_time = snapshot.get("snapshot_time", "unknown")
    lines.append(f"Snapshot taken at {snap_time}.\n")

    telemetry = snapshot.get("telemetry", {})
    analytics = snapshot.get("analytics", {})

    # --- TELEMETRY SECTION (Natural Language Style) ---
    for team, drivers in telemetry.items():
        for driver, metrics in drivers.items():

            circuit = metrics.get("circuit", {}).get("value", "unknown circuit")
            lap = metrics.get("lap", {}).get("value")
            speed = metrics.get("speed", {}).get("value")
            rpm = metrics.get("rpm", {}).get("value")
            fuel = metrics.get("fuel_level", {}).get("value")
            gear = metrics.get("gear", {}).get("value")
            drs = metrics.get("drs", {}).get("value")
            accident = metrics.get("accident", {}).get("value")

            sentence = f"{driver.capitalize()} from {team.capitalize()} is racing at {circuit}."

            if lap:
                sentence += f" He is currently on lap {lap}."
            if speed:
                sentence += f" His speed is {speed} km/h."
            if rpm:
                sentence += f" Engine RPM is {rpm}."
            if gear:
                sentence += f" Gear position is {gear}."
            if fuel:
                sentence += f" Remaining fuel is {fuel} kg."
            if drs is not None:
                sentence += f" DRS status is {drs}."
            if accident == "1":
                sentence += " An accident has been detected."

            lines.append(sentence)

    # --- ANALYTICS SECTION ---
    leader = analytics.get("leader_driver", {}).get("value")
    leader_lap = analytics.get("leader_lap", {}).get("value")
    fastest = analytics.get("fastest_driver", {}).get("value")
    fastest_speed = analytics.get("fastest_speed", {}).get("value")

    if leader:
        lines.append(f"The current race leader is {leader} on lap {leader_lap}.")
    if fastest:
        lines.append(f"The fastest driver is {fastest} with a speed of {fastest_speed} km/h.")

    return "\n".join(lines)


# =========================================
# SNAPSHOT CHUNKING
# =========================================

def chunk_snapshots():
    snapshot_files = sorted(glob.glob(os.path.join(SNAPSHOT_DIR, "snapshot_*.json")))

    print("\n===================================")
    print(" Chunking Snapshots")
    print("Snapshot dir:", os.path.abspath(SNAPSHOT_DIR))
    print("Found snapshot files:", len(snapshot_files))
    print("Output folder:", os.path.abspath(SNAPSHOT_CHUNKS_DIR))
    print("===================================")

    if not snapshot_files:
        print(" No snapshot files found. Check SNAPSHOT_DIR path.")
        return

    chunk_index = 1
    buffer_texts = []

    for fp in snapshot_files:
        snap = safe_read_json(fp)
        if not snap:
            continue

        buffer_texts.append(format_snapshot_to_text(snap))

        if len(buffer_texts) >= SNAPSHOTS_PER_CHUNK:
            out_file = os.path.join(SNAPSHOT_CHUNKS_DIR, f"snapshot_chunk_{chunk_index:04d}.txt")
            with open(out_file, "w", encoding="utf-8") as f:
                f.write("\n\n".join(buffer_texts))
            print(f" Wrote: {out_file}")
            chunk_index += 1
            buffer_texts = []

    # Write remaining snapshots
    if buffer_texts:
        out_file = os.path.join(SNAPSHOT_CHUNKS_DIR, f"snapshot_chunk_{chunk_index:04d}.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n\n".join(buffer_texts))
        print(f" Wrote: {out_file}")

    print(" Snapshot chunking complete.")


# =========================================
# EVENT CHUNKING
# =========================================

def chunk_events():
    if not os.path.exists(EVENT_LOG_FILE):
        print("\n No event log found at:", os.path.abspath(EVENT_LOG_FILE))
        print("Skipping event chunking.")
        return

    with open(EVENT_LOG_FILE, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    if not lines:
        print(" Event file is empty. Skipping.")
        return

    print("\n===================================")
    print(" Chunking Event Logs")
    print("Event file:", os.path.abspath(EVENT_LOG_FILE))
    print("Output folder:", os.path.abspath(EVENT_CHUNKS_DIR))
    print("===================================")

    chunk_index = 1
    for i in range(0, len(lines), EVENTS_PER_CHUNK):
        chunk_lines = lines[i:i + EVENTS_PER_CHUNK]
        out_file = os.path.join(EVENT_CHUNKS_DIR, f"event_chunk_{chunk_index:04d}.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(chunk_lines))
        print(f" Wrote: {out_file}")
        chunk_index += 1

    print("🎉 Event chunking complete.")


# =========================================
# MAIN
# =========================================

def main():
    ensure_dirs()
    chunk_snapshots()
    chunk_events()


if __name__ == "__main__":
    main()