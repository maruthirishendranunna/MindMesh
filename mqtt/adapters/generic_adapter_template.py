"""
GENERIC ADAPTER TEMPLATE

👉 Copy this file and rename:
    hospital_adapter.py
    football_adapter.py
    oilgas_adapter.py

👉 Then update ONLY:
    - topic structure
    - entities
    - metrics
    - event rules

Everything else stays same.
"""

import os
import json

# =========================
# CONFIG (CHANGE PER DATASET)
# =========================

INPUT_TOPICS_PROCESSOR = ["<domain>/#"]
INPUT_TOPICS_SNAPSHOTTER = ["<domain>/#", "<analytics>/#"]
ANALYTICS_PREFIX = "<analytics>"

SNAPSHOTS_PER_CHUNK = 5
EVENTS_PER_CHUNK = 10


# =========================
# BASIC HELPERS
# =========================

def safe_float(x):
    try:
        return float(x)
    except:
        return None


def safe_int(x):
    try:
        return int(float(x))
    except:
        return None


# =========================
# QUERY NORMALIZATION
# =========================

def normalize_question_text(question: str) -> str:
    q = question.lower().strip()

    # 👉 Add dataset-specific corrections here
    replacements = {
        # Example:
        # "temprature": "temperature"
    }

    for wrong, correct in replacements.items():
        q = q.replace(wrong, correct)

    return q


# =========================
# TOPIC PARSING
# =========================

def parse_topic(topic: str):
    """
    Expected format:
    <domain>/<entity>/<sub_entity>/<metric>

    Example:
    hospital/patient1/heart_rate
    oilgas/site1/pump1/pressure
    football/team1/player1/speed
    """
    parts = topic.split("/")

    if len(parts) != 4:
        return None

    if parts[0] != "<domain>":
        return None

    return parts[1], parts[2], parts[3]


# =========================
# ENTITY EXTRACTION
# =========================

def extract_entities(question: str) -> dict:
    q = normalize_question_text(question)

    # 👉 Customize for dataset
    entities = {
        "entity": None,
        "sub_entity": None
    }

    # Example:
    # if "patient1" in q: entities["entity"] = "patient1"

    return entities


# =========================
# QUERY CLASSIFICATION
# =========================

def classify_query(question: str) -> str:
    q = normalize_question_text(question)

    comparison_words = ["highest", "lowest", "max", "min", "top", "best"]
    event_words = ["alert", "event", "fault", "abnormal"]

    if any(w in q for w in comparison_words):
        return "comparison"

    if any(w in q for w in event_words):
        return "event"

    return "metric"


# =========================
# DIRECT ANSWER CONTROL
# =========================

def can_handle_directly(question: str) -> bool:
    q = normalize_question_text(question)

    keywords = [
        "highest", "lowest", "max", "min",
        "pressure", "temperature", "speed", "status"
    ]

    if "what about" in q:
        return True

    return any(k in q for k in keywords)


def get_direct_answer(question: str, context: str):
    q = normalize_question_text(question)

    # 👉 Implement dataset logic here
    return None


# =========================
# ANALYTICS (OPTIONAL)
# =========================

def compute_analytics_from_cache(topic_cache: dict):
    """
    Example:
    - highest value
    - average
    """
    return {}


def publish_analytics(client, analytics: dict):
    """
    Publish computed analytics to MQTT
    """
    pass


# =========================
# SNAPSHOT BUILDING
# =========================

def build_snapshot_from_cache(topic_cache: dict, snapshot_time: str):
    snapshot = {
        "snapshot_time": snapshot_time,
        "telemetry": {},
        "analytics": {}
    }

    for topic, record in topic_cache.items():
        parsed = parse_topic(topic)

        if not parsed:
            continue

        entity, sub_entity, metric = parsed

        snapshot["telemetry"].setdefault(entity, {})
        snapshot["telemetry"][entity].setdefault(sub_entity, {})
        snapshot["telemetry"][entity][sub_entity][metric] = record

    return snapshot


# =========================
# EVENT DETECTION
# =========================

def detect_events(snapshot: dict, last_seen: dict, log_event_callback):
    """
    👉 Define dataset-specific event rules

    Example:
    if temperature > threshold → log event
    """
    pass


# =========================
# SNAPSHOT → TEXT
# =========================

def format_snapshot_to_text(snapshot: dict) -> str:
    lines = []

    snap_time = snapshot.get("snapshot_time", "unknown")
    lines.append(f"Snapshot time: {snap_time}.")

    telemetry = snapshot.get("telemetry", {})

    for entity, sub_entities in telemetry.items():
        for sub_entity, metrics in sub_entities.items():

            # 👉 Customize output format
            metric_text = ", ".join(
                f"{k}={v.get('value', 'unknown')}"
                for k, v in metrics.items()
            )

            lines.append(
                f"{entity}/{sub_entity}: {metric_text}"
            )

    return "\n".join(lines)


# =========================
# EVENT → TEXT
# =========================

def format_event_line(event_line: str) -> str:
    try:
        event = json.loads(event_line)

        timestamp = event.get("timestamp", "unknown")
        event_type = event.get("type", "UNKNOWN")
        data = event.get("data", {})

        return f"Event {event_type} at {timestamp}: {data}"

    except:
        return event_line