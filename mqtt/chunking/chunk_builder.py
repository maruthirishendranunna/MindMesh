import os
import json
import glob
from mqtt.adapters.loader import get_adapter

adapter = get_adapter()

SNAPSHOT_DIR = os.path.join("mqtt", "processor", "data", "snapshots")
EVENT_LOG_FILE = os.path.join("mqtt", "processor", "data", "events", "events.jsonl")

CHUNKS_DIR = os.path.join("data", "chunks")
SNAPSHOT_CHUNKS_DIR = os.path.join(CHUNKS_DIR, "snapshots")
EVENT_CHUNKS_DIR = os.path.join(CHUNKS_DIR, "events")

SNAPSHOTS_PER_CHUNK = adapter.SNAPSHOTS_PER_CHUNK
EVENTS_PER_CHUNK = adapter.EVENTS_PER_CHUNK


def ensure_dirs():
    os.makedirs(SNAPSHOT_CHUNKS_DIR, exist_ok=True)
    os.makedirs(EVENT_CHUNKS_DIR, exist_ok=True)


def safe_read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to read JSON: {path} | {e}")
        return None


def chunk_snapshots():
    snapshot_files = sorted(glob.glob(os.path.join(SNAPSHOT_DIR, "snapshot_*.json")))

    print("\n===================================")
    print("📌 Chunking Snapshots")
    print("Snapshot dir:", os.path.abspath(SNAPSHOT_DIR))
    print("Found snapshot files:", len(snapshot_files))
    print("Output folder:", os.path.abspath(SNAPSHOT_CHUNKS_DIR))
    print("===================================")

    if not snapshot_files:
        print("⚠️ No snapshot files found. Check SNAPSHOT_DIR path.")
        return

    chunk_index = 1
    buffer_texts = []

    for fp in snapshot_files:
        snap = safe_read_json(fp)
        if not snap:
            continue

        buffer_texts.append(adapter.format_snapshot_to_text(snap))

        if len(buffer_texts) >= SNAPSHOTS_PER_CHUNK:
            out_file = os.path.join(SNAPSHOT_CHUNKS_DIR, f"snapshot_chunk_{chunk_index:04d}.txt")
            with open(out_file, "w", encoding="utf-8") as f:
                f.write("\n\n".join(buffer_texts))
            print(f"✅ Wrote: {out_file}")
            chunk_index += 1
            buffer_texts = []

    if buffer_texts:
        out_file = os.path.join(SNAPSHOT_CHUNKS_DIR, f"snapshot_chunk_{chunk_index:04d}.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n\n".join(buffer_texts))
        print(f"✅ Wrote: {out_file}")

    print("🎉 Snapshot chunking complete.")


def chunk_events():
    if not os.path.exists(EVENT_LOG_FILE):
        print("\n⚠️ No event log found at:", os.path.abspath(EVENT_LOG_FILE))
        print("Skipping event chunking.")
        return

    with open(EVENT_LOG_FILE, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    if not lines:
        print("⚠️ Event file is empty. Skipping.")
        return

    print("\n===================================")
    print("📌 Chunking Event Logs")
    print("Event file:", os.path.abspath(EVENT_LOG_FILE))
    print("Output folder:", os.path.abspath(EVENT_CHUNKS_DIR))
    print("===================================")

    chunk_index = 1
    for i in range(0, len(lines), EVENTS_PER_CHUNK):
        chunk_lines = lines[i:i + EVENTS_PER_CHUNK]
        formatted_lines = [adapter.format_event_line(line) for line in chunk_lines]

        out_file = os.path.join(EVENT_CHUNKS_DIR, f"event_chunk_{chunk_index:04d}.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(formatted_lines))
        print(f"✅ Wrote: {out_file}")
        chunk_index += 1

    print("🎉 Event chunking complete.")


def main():
    ensure_dirs()
    chunk_snapshots()
    chunk_events()


if __name__ == "__main__":
    main()