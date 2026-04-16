import os
import json
import re
from collections import defaultdict

# =========================
# DATASET-SPECIFIC CONFIG
# =========================

INPUT_TOPICS_PROCESSOR = ["f1/#"]
INPUT_TOPICS_SNAPSHOTTER = ["f1/#", "race/#"]
ANALYTICS_PREFIX = "race"

SNAPSHOTS_PER_CHUNK = 5
EVENTS_PER_CHUNK = 10

TEMPLATE_DIR = os.path.join("mqtt", "adapters", "templates")


# =========================
# TEMPLATE HELPERS
# =========================

def load_template(filename: str) -> str:
    path = os.path.join(TEMPLATE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


# =========================
# BASIC HELPERS
# =========================

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def safe_int(x):
    try:
        return int(float(x))
    except Exception:
        return None


# =========================
# QUERY NORMALIZATION
# =========================

def normalize_question_text(question: str) -> str:
    q = question.lower().strip()

    replacements = {
        "spped": "speed",
        "sliverstone": "silverstone",
        "happend": "happened",
        "accidents happend": "accidents happened",
        "accident happend": "accident happened",
        "who as": "who has",
        "top speed": "highest speed",
        "best speed": "highest speed",
        "fastest speed": "highest speed",
        "top rpm": "highest rpm",
        "best rpm": "highest rpm",
        "lowest fuel level": "lowest fuel",
        "best lap speed": "highest speed",
    }

    for wrong, correct in replacements.items():
        q = q.replace(wrong, correct)

    return q


# =========================
# TOPIC PARSING
# =========================

def parse_topic(topic: str):
    """
    Expected topic format:
    f1/<team>/<driver>/<metric>
    """
    parts = topic.split("/")
    if len(parts) != 4:
        return None
    if parts[0] != "f1":
        return None
    return parts[1], parts[2], parts[3]


def build_search_query_from_topic(topic: str, original_question: str) -> str:
    """
    Convert adapter-specific topic format into a retrieval-friendly search query.
    """
    if not topic:
        return normalize_question_text(original_question)

    parts = topic.split("/")

    if len(parts) >= 4 and parts[0] == "f1":
        return " ".join(parts[1:])

    return normalize_question_text(original_question)


def build_telemetry_query_from_topics(original_question: str, topic_docs) -> str:
    """
    Choose the best topic match for the question and convert it into
    a retrieval-friendly telemetry query.
    """
    normalized_question = normalize_question_text(original_question)

    if not topic_docs:
        return normalized_question

    q = normalized_question

    preferred_metric = None
    metric_keywords = [
        "speed", "rpm", "gear", "fuel",
        "drs", "lap", "circuit", "sector"
    ]

    for metric in metric_keywords:
        if metric in q:
            preferred_metric = metric
            break

    best_topic = None

    if preferred_metric:
        for doc in topic_docs:
            topic = doc.metadata.get("topic", "").lower()
            if preferred_metric in topic:
                best_topic = doc.metadata.get("topic", "")
                break

    if not best_topic:
        best_topic = topic_docs[0].metadata.get("topic", "")

    if not best_topic:
        return normalized_question

    base_query = build_search_query_from_topic(best_topic, normalized_question)
    entities = extract_entities(normalized_question)

    if entities.get("circuit"):
        return f"{base_query} {entities['circuit']}"

    return base_query


# =========================
# ENTITY EXTRACTION (Pranith Week-7)
# =========================

def extract_entities(question: str) -> dict:
    q = normalize_question_text(question)

    drivers = [
        "verstappen", "perez",
        "hamilton", "russell",
        "norris", "piastri",
        "alonso", "stroll"
    ]

    teams = [
        "redbull",
        "mercedes",
        "mclaren",
        "astonmartin"
    ]

    circuits = [
        "monza",
        "silverstone",
        "spa-francorchamps",
        "spa",
        "bahrain"
    ]

    found_driver = next((d for d in drivers if d in q), None)
    found_team = next((t for t in teams if t in q), None)
    found_circuit = next((c for c in circuits if c in q), None)

    return {
        "driver": found_driver,
        "team": found_team,
        "circuit": found_circuit
    }


# =========================
# QUERY UNDERSTANDING
# =========================

def classify_query(question: str) -> str:
    q = normalize_question_text(question)

    event_words = [
        "accident", "crash", "winner", "won",
        "leader changed", "fastest changed",
        "lap changed", "event", "leader"
    ]

    comparison_words = [
        "highest", "lowest", "maximum", "minimum",
        "max", "min", "top", "best", "fastest"
    ]

    metric_words = [
        "rpm", "speed", "fuel", "gear",
        "lap", "drs", "circuit", "sector"
    ]

    if any(w in q for w in comparison_words):
        return "comparison"

    if any(w in q for w in event_words):
        return "event"

    if any(w in q for w in metric_words):
        return "metric"

    return "general"


def detect_metric_name(question: str) -> str | None:
    q = normalize_question_text(question)

    metric_map = [
        ("speed", "speed"),
        ("rpm", "rpm"),
        ("gear", "gear"),
        ("fuel", "fuel"),
        ("drs", "drs"),
        ("lap", "lap"),
        ("sector", "sector"),
        ("circuit", "circuit"),
    ]

    for key, value in metric_map:
        if key in q:
            return value

    return None


def filter_telemetry_lines(original_question: str, refined_question: str, text: str):
    """
    Dataset-specific filtering for telemetry lines before sending context to LLM.
    Supports multi-condition filtering using extracted entities.
    """
    if not text:
        return []

    normalized_question = normalize_question_text(original_question)
    query_type = classify_query(normalized_question)
    entities = extract_entities(normalized_question)

    driver = entities.get("driver")
    team = entities.get("team")
    circuit = entities.get("circuit")

    question_tokens = set(normalized_question.split())
    lines_split = text.split("\n")
    filtered_lines = []

    for line in lines_split:
        line_lower = line.lower()

        driver_match = True if not driver else driver in line_lower
        team_match = True if not team else team in line_lower
        circuit_match = True if not circuit else circuit in line_lower

        if query_type == "event":
            event_match = False

            if "accident" in question_tokens or "crash" in question_tokens:
                if "accident" in line_lower or "crash" in line_lower:
                    event_match = True

            elif "winner" in question_tokens or "won" in question_tokens:
                if "winner" in line_lower or "race finished" in line_lower:
                    event_match = True

            elif "leader" in question_tokens:
                if "leader" in line_lower:
                    event_match = True

            elif "lap" in question_tokens and "changed" in question_tokens:
                if "lap changed" in line_lower:
                    event_match = True

            else:
                event_match = True

            if event_match and driver_match and team_match and circuit_match:
                filtered_lines.append(line)

        elif query_type in ("metric", "comparison"):
            metric_match = False

            if "speed" in question_tokens and "speed" in line_lower:
                metric_match = True
            elif "rpm" in question_tokens and "rpm" in line_lower:
                metric_match = True
            elif "gear" in question_tokens and "gear" in line_lower:
                metric_match = True
            elif "fuel" in question_tokens and "fuel" in line_lower:
                metric_match = True
            elif "drs" in question_tokens and "drs" in line_lower:
                metric_match = True
            elif "lap" in question_tokens and "lap" in line_lower:
                metric_match = True
            elif "circuit" in question_tokens and "circuit" in line_lower:
                metric_match = True
            elif "sector" in question_tokens and "sector" in line_lower:
                metric_match = True

            if metric_match and driver_match and team_match and circuit_match:
                filtered_lines.append(line)

        else:
            if driver_match and team_match and circuit_match:
                filtered_lines.append(line)

    return filtered_lines


# =========================
# DIRECT ANSWER HANDLING
# =========================

def can_handle_directly(question: str) -> bool:
    q = normalize_question_text(question)

    # Handle follow-up queries
    if "what about" in q or "other drivers" in q:
        return True

    deterministic_keywords = [
        "accident", "accidents", "crash", "crashes",
        "highest", "maximum", "lowest", "minimum",
        "max", "min", "top", "best", "fastest",
        "speed", "rpm", "fuel", "gear", "drs", "lap", "sector", "circuit"
    ]

    return any(k in q for k in deterministic_keywords)


def get_direct_answer(question: str, context: str) -> str | None:
    q = normalize_question_text(question)

    # Follow-up queries
    if "what about" in q or "other drivers" in q:
        return get_next_best_entities(context)

    query_type = classify_query(q)

    # Event queries
    if "accident" in q or "accidents" in q or "crash" in q or "crashes" in q:
        return format_accident_answer(q, context)

    # Comparison queries
    if query_type == "comparison":
        result = compute_best_metric_answer(q, context)
        if result:
            return result

    # Metric queries
    if query_type == "metric":
        result = format_metric_answer(q, context)
        if result:
            return result

    return None

def get_next_best_entities(context: str):
    import re

    matches = re.findall(r"Driver (\w+).*?Speed is ([0-9.]+)", context)

    if not matches:
        return None

    # Keep only highest speed per driver
    driver_speeds = {}

    for driver, speed in matches:
        speed = float(speed)

        if driver not in driver_speeds:
            driver_speeds[driver] = speed
        else:
            driver_speeds[driver] = max(driver_speeds[driver], speed)

    # Sort descending
    ranked = sorted(driver_speeds.items(), key=lambda x: x[1], reverse=True)

    if len(ranked) <= 1:
        return "No other relevant data found."

    # Remove top one
    remaining = ranked[1:]

    lines = ["Other top speeds:"]
    for driver, speed in remaining[:5]:
        lines.append(f"- {driver.capitalize()}: {speed} km/h")

    return "\n".join(lines)

# =========================
# EVENT ANSWERS
# =========================

def extract_circuit_from_question(question: str) -> str | None:
    return extract_entities(question).get("circuit")


def normalize_driver_name(driver_key: str) -> str:
    parts = [p.strip() for p in driver_key.split("/") if p.strip()]
    parts = [p.capitalize() for p in parts]
    return "/".join(parts)


def extract_accident_events(context: str):
    pattern = (
        r"Accident detected\.\s*Driver\s+([a-zA-Z0-9_/-]+)\s+had accident "
        r"at circuit\s+([a-zA-Z0-9_.\- ]+)\s+lap\s+([0-9]+)\s+sector\s+([0-9]+)\."
    )

    matches = re.findall(pattern, context, flags=re.IGNORECASE)

    events = []
    for driver, circuit, lap, sector in matches:
        events.append({
            "driver": driver.strip(),
            "circuit": circuit.strip(),
            "lap": lap.strip(),
            "sector": sector.strip()
        })

    return events


def format_accident_answer(question: str, context: str) -> str | None:
    events = extract_accident_events(context)

    if not events:
        return "No, no accident data was found."

    requested_circuit = extract_circuit_from_question(question)

    if requested_circuit:
        filtered = [e for e in events if requested_circuit in e["circuit"].lower()]
    else:
        filtered = events

    if not filtered:
        if requested_circuit:
            return f"No, no accidents were found in {requested_circuit.capitalize()}."
        return "No, no accidents were found."

    parts = []
    for e in filtered:
        driver = normalize_driver_name(e["driver"])
        circuit = e["circuit"]
        lap = e["lap"]
        sector = e["sector"]
        parts.append(f"{driver} had an accident at {circuit} on lap {lap} in sector {sector}")

    if requested_circuit:
        intro = f"Yes, accidents occurred in {filtered[0]['circuit']}."
    else:
        intro = "Yes, accidents occurred."

    return intro + " " + "; ".join(parts) + "."


# =========================
# METRIC EXTRACTION
# =========================

def extract_metric_records(context: str):
    pattern = (
        r"Driver\s+(\w+)\s+from team\s+(\w+)\s+is racing at circuit\s+([a-zA-Z0-9_.\- ]+)\.\s*"
        r"Current lap is\s+([0-9]+)\.\s*"
        r"Speed is\s+([0-9.]+)\s+km/h\.\s*"
        r"RPM is\s+([0-9.]+)\.\s*"
        r"Gear is\s+([0-9]+)\.\s*"
        r"Fuel level is\s+([0-9.]+)\.\s*"
        r"DRS is\s+([0-9]+)\."
    )

    matches = re.findall(pattern, context, flags=re.IGNORECASE)

    records = []
    for driver, team, circuit, lap, speed, rpm, gear, fuel, drs in matches:
        try:
            records.append({
                "driver": driver.strip(),
                "team": team.strip(),
                "circuit": circuit.strip(),
                "lap": int(lap),
                "speed": float(speed),
                "rpm": float(rpm),
                "gear": int(gear),
                "fuel": float(fuel),
                "drs": int(drs)
            })
        except ValueError:
            continue

    return records


def format_metric_value(metric_name: str, record: dict):
    if metric_name == "speed":
        return f"{record['speed']} km/h"
    if metric_name == "rpm":
        return f"{record['rpm']}"
    if metric_name == "gear":
        return f"{record['gear']}"
    if metric_name == "fuel":
        return f"{record['fuel']}"
    if metric_name == "drs":
        return f"{record['drs']}"
    if metric_name == "lap":
        return f"{record['lap']}"
    if metric_name == "circuit":
        return f"{record['circuit']}"
    return None


# =========================
# COMPARISON ANSWERS
# =========================

def compute_best_metric_answer(question: str, context: str) -> str | None:
    records = extract_metric_records(context)
    if not records:
        return None

    q = normalize_question_text(question)
    metric_name = detect_metric_name(q)
    if not metric_name:
        return None

    entities = extract_entities(q)
    driver = entities.get("driver")
    team = entities.get("team")
    circuit = entities.get("circuit")

    filtered = []
    for r in records:
        driver_match = True if not driver else driver == r["driver"].lower()
        team_match = True if not team else team == r["team"].lower()
        circuit_match = True if not circuit else circuit in r["circuit"].lower()

        if driver_match and team_match and circuit_match:
            filtered.append(r)

    if not filtered:
        return None

    if metric_name not in {"speed", "rpm", "gear", "fuel", "drs", "lap"}:
        return None

    is_lowest = any(word in q for word in ["lowest", "minimum", "least", "min"])

    if is_lowest:
        best = min(filtered, key=lambda x: x[metric_name])
        mode_text = "lowest"
    else:
        best = max(filtered, key=lambda x: x[metric_name])
        mode_text = "highest"

    value = format_metric_value(metric_name, best)
    driver_name = best["driver"].capitalize()
    circuit_name = best["circuit"]

    if metric_name == "speed":
        return f"{driver_name} has the {mode_text} recorded speed in {circuit_name}: {value} on lap {best['lap']}."
    if metric_name == "rpm":
        return f"{driver_name} has the {mode_text} recorded RPM in {circuit_name}: {value} on lap {best['lap']}."
    if metric_name == "gear":
        return f"{driver_name} has the {mode_text} recorded gear in {circuit_name}: {value} on lap {best['lap']}."
    if metric_name == "fuel":
        return f"{driver_name} has the {mode_text} recorded fuel level in {circuit_name}: {value} on lap {best['lap']}."
    if metric_name == "drs":
        return f"{driver_name} has the {mode_text} recorded DRS value in {circuit_name}: {value} on lap {best['lap']}."
    if metric_name == "lap":
        return f"{driver_name} has the {mode_text} recorded lap value in {circuit_name}: {value}."

    return None


# =========================
# DIRECT METRIC ANSWERS
# =========================

def format_metric_answer(question: str, context: str) -> str | None:
    records = extract_metric_records(context)
    if not records:
        return None

    q = normalize_question_text(question)
    entities = extract_entities(q)
    driver = entities.get("driver")
    team = entities.get("team")
    circuit = entities.get("circuit")
    metric_name = detect_metric_name(q)

    if not metric_name:
        return None

    filtered = []
    for r in records:
        driver_match = True if not driver else driver == r["driver"].lower()
        team_match = True if not team else team == r["team"].lower()
        circuit_match = True if not circuit else circuit in r["circuit"].lower()

        if driver_match and team_match and circuit_match:
            filtered.append(r)

    if not filtered:
        return None

    latest = max(filtered, key=lambda x: x["lap"])
    value = format_metric_value(metric_name, latest)

    if value is None:
        return None

    driver_name = latest["driver"].capitalize()
    circuit_name = latest["circuit"]

    if metric_name == "speed":
        return f"{driver_name}'s speed in {circuit_name} is {value}."
    if metric_name == "rpm":
        return f"{driver_name}'s RPM in {circuit_name} is {value}."
    if metric_name == "gear":
        return f"{driver_name}'s gear in {circuit_name} is {value}."
    if metric_name == "fuel":
        return f"{driver_name}'s fuel level in {circuit_name} is {value}."
    if metric_name == "drs":
        return f"{driver_name}'s DRS status in {circuit_name} is {value}."
    if metric_name == "lap":
        return f"{driver_name} is on lap {value} in {circuit_name}."
    if metric_name == "circuit":
        return f"{driver_name} is racing at {value}."

    return None


# =========================
# DRIVER MAP
# =========================

def build_driver_map(topic_cache: dict):
    drivers = {}

    for topic, value in topic_cache.items():
        parsed = parse_topic(topic)
        if not parsed:
            continue

        team, driver, metric = parsed
        key = f"{team}/{driver}"
        drivers.setdefault(key, {})
        drivers[key][metric] = value

    return drivers


# =========================
# ANALYTICS
# =========================

def compute_fastest_driver(drivers: dict):
    fastest_driver = None
    fastest_speed = -1.0
    fastest_circuit = None

    for driver_key, metrics in drivers.items():
        sp = safe_float(metrics.get("speed"))
        if sp is None:
            continue

        if sp > fastest_speed:
            fastest_speed = sp
            fastest_driver = driver_key
            fastest_circuit = metrics.get("circuit")

    return fastest_driver, fastest_speed, fastest_circuit


def compute_leader(drivers: dict):
    leader = None
    leader_lap = -1
    leader_circuit = None

    for driver_key, metrics in drivers.items():
        lap = safe_int(metrics.get("lap"))
        if lap is None:
            continue

        if lap > leader_lap:
            leader_lap = lap
            leader = driver_key
            leader_circuit = metrics.get("circuit")

    return leader, leader_lap, leader_circuit


def compute_team_avg_speed(drivers: dict):
    team_speeds = defaultdict(list)

    for driver_key, metrics in drivers.items():
        team = driver_key.split("/")[0]
        sp = safe_float(metrics.get("speed"))
        if sp is None:
            continue
        team_speeds[team].append(sp)

    team_avg = {}
    for team, speeds in team_speeds.items():
        if speeds:
            team_avg[team] = sum(speeds) / len(speeds)

    return team_avg


def compute_analytics_from_cache(topic_cache: dict):
    drivers = build_driver_map(topic_cache)

    if not drivers:
        return None

    fastest_driver, fastest_speed, fastest_circuit = compute_fastest_driver(drivers)
    leader, leader_lap, leader_circuit = compute_leader(drivers)
    team_avg = compute_team_avg_speed(drivers)

    return {
        "drivers": drivers,
        "fastest_driver": fastest_driver,
        "fastest_speed": fastest_speed,
        "fastest_circuit": fastest_circuit,
        "leader": leader,
        "leader_lap": leader_lap,
        "leader_circuit": leader_circuit,
        "team_avg": team_avg
    }


def publish_analytics(client, analytics: dict):
    fastest_driver = analytics["fastest_driver"]
    fastest_speed = analytics["fastest_speed"]
    fastest_circuit = analytics["fastest_circuit"]
    leader = analytics["leader"]
    leader_lap = analytics["leader_lap"]
    leader_circuit = analytics["leader_circuit"]
    team_avg = analytics["team_avg"]

    client.publish(f"{ANALYTICS_PREFIX}/fastest_driver", fastest_driver or "unknown", qos=0, retain=False)
    client.publish(
        f"{ANALYTICS_PREFIX}/fastest_speed",
        round(fastest_speed, 2) if fastest_speed is not None and fastest_speed >= 0 else "unknown",
        qos=0,
        retain=False
    )
    client.publish(f"{ANALYTICS_PREFIX}/leader_driver", leader or "unknown", qos=0, retain=False)
    client.publish(
        f"{ANALYTICS_PREFIX}/leader_lap",
        leader_lap if leader_lap is not None and leader_lap >= 0 else "unknown",
        qos=0,
        retain=False
    )

    for team, avg in team_avg.items():
        client.publish(f"{ANALYTICS_PREFIX}/team_avg_speed/{team}", round(avg, 2), qos=0, retain=False)

    if fastest_circuit and fastest_driver:
        client.publish(f"{ANALYTICS_PREFIX}/{fastest_circuit}/fastest_driver", fastest_driver, qos=0, retain=False)
        client.publish(f"{ANALYTICS_PREFIX}/{fastest_circuit}/fastest_speed", round(fastest_speed, 2), qos=0, retain=False)

    if leader_circuit and leader:
        client.publish(f"{ANALYTICS_PREFIX}/{leader_circuit}/leader_driver", leader, qos=0, retain=False)
        client.publish(f"{ANALYTICS_PREFIX}/{leader_circuit}/leader_lap", leader_lap, qos=0, retain=False)


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
        parts = topic.split("/")

        if parts[0] == "f1" and len(parts) >= 4:
            team = parts[1]
            driver = parts[2]
            metric = parts[3]

            snapshot["telemetry"].setdefault(team, {})
            snapshot["telemetry"][team].setdefault(driver, {})
            snapshot["telemetry"][team][driver][metric] = record

        elif parts[0] == ANALYTICS_PREFIX:
            metric = "/".join(parts[1:])
            snapshot["analytics"][metric] = record

    return snapshot


# =========================
# EVENT DETECTION
# =========================

def detect_events(snapshot: dict, last_seen: dict, log_event_callback):
    analytics = snapshot.get("analytics", {})
    telemetry = snapshot.get("telemetry", {})

    leader_driver = analytics.get("leader_driver", {}).get("value")
    leader_lap = analytics.get("leader_lap", {}).get("value")
    leader_tuple = (leader_driver, leader_lap)

    if leader_driver and leader_tuple != last_seen["race_leader"]:
        log_event_callback("RACE_LEADER_CHANGED", {
            "leader": leader_driver,
            "lap": leader_lap
        })
        last_seen["race_leader"] = leader_tuple

    fastest_driver = analytics.get("fastest_driver", {}).get("value")
    fastest_speed = analytics.get("fastest_speed", {}).get("value")
    fastest_tuple = (fastest_driver, fastest_speed)

    if fastest_driver and fastest_tuple != last_seen["fastest"]:
        log_event_callback("FASTEST_DRIVER_CHANGED", {
            "fastest_driver": fastest_driver,
            "fastest_speed": fastest_speed
        })
        last_seen["fastest"] = fastest_tuple

    for team, drivers in telemetry.items():
        for driver, metrics in drivers.items():
            key = f"{team}/{driver}"

            circuit = metrics.get("circuit", {}).get("value")
            lap_val = safe_int(metrics.get("lap", {}).get("value"))
            race_laps = safe_int(metrics.get("race_laps", {}).get("value"))
            sector = metrics.get("sector", {}).get("value")

            if lap_val is not None:
                prev_lap = last_seen["driver_laps"].get(key)
                if prev_lap is None:
                    last_seen["driver_laps"][key] = lap_val
                elif lap_val != prev_lap:
                    log_event_callback("LAP_CHANGED", {
                        "driver": key,
                        "from": prev_lap,
                        "to": lap_val,
                        "circuit": circuit
                    })
                    last_seen["driver_laps"][key] = lap_val

            acc_val = safe_int(metrics.get("accident", {}).get("value"))
            if acc_val is not None:
                prev_acc = last_seen["driver_accident"].get(key, 0)
                if prev_acc == 0 and acc_val == 1:
                    log_event_callback("ACCIDENT_DETECTED", {
                        "driver": key,
                        "circuit": circuit,
                        "lap": lap_val,
                        "sector": sector
                    })
                last_seen["driver_accident"][key] = acc_val

            if circuit and lap_val is not None and race_laps is not None:
                if lap_val >= race_laps:
                    winner_key = (circuit, key)
                    if winner_key not in last_seen["winners"]:
                        log_event_callback("WINNER_DECIDED", {
                            "circuit": circuit,
                            "winner": key,
                            "race_laps": race_laps
                        })
                        last_seen["winners"].add(winner_key)


# =========================
# CHUNK FORMATTING
# =========================

def format_snapshot_to_text(snapshot: dict) -> str:
    lines = []

    snap_time = snapshot.get("snapshot_time", "unknown")
    lines.append(f"Snapshot time: {snap_time}.")

    telemetry = snapshot.get("telemetry", {})
    analytics = snapshot.get("analytics", {})

    for team, drivers in telemetry.items():
        for driver, metrics in drivers.items():
            circuit = metrics.get("circuit", {}).get("value", "unknown")
            lap = metrics.get("lap", {}).get("value", "unknown")
            speed = metrics.get("speed", {}).get("value", "unknown")
            rpm = metrics.get("rpm", {}).get("value", "unknown")
            gear = metrics.get("gear", {}).get("value", "unknown")
            fuel = metrics.get("fuel_level", {}).get("value", "unknown")
            drs = metrics.get("drs", {}).get("value", "unknown")
            accident = metrics.get("accident", {}).get("value", "0")

            sentence = (
                f"Driver {driver} from team {team} is racing at circuit {circuit}. "
                f"Current lap is {lap}. "
                f"Speed is {speed} km/h. "
                f"RPM is {rpm}. "
                f"Gear is {gear}. "
                f"Fuel level is {fuel}. "
                f"DRS is {drs}."
            )

            if accident == "1":
                sentence += " Accident detected."

            lines.append(sentence)

    leader = analytics.get("leader_driver", {}).get("value")
    leader_lap = analytics.get("leader_lap", {}).get("value")
    fastest = analytics.get("fastest_driver", {}).get("value")
    fastest_speed = analytics.get("fastest_speed", {}).get("value")

    if leader:
        lines.append(f"Race leader is {leader} on lap {leader_lap}.")

    if fastest:
        lines.append(f"Fastest driver is {fastest} with speed {fastest_speed} km/h.")

    return "\n".join(lines)


def format_event_line(event_line: str) -> str:
    try:
        event = json.loads(event_line)

        timestamp = event.get("timestamp", "unknown")
        event_type = event.get("type", "UNKNOWN")
        data = event.get("data", {})

        if event_type == "RACE_LEADER_CHANGED":
            return (
                f"Race leader changed. "
                f"At {timestamp}, leader is {data.get('leader')} "
                f"on lap {data.get('lap')}."
            )

        elif event_type == "FASTEST_DRIVER_CHANGED":
            return (
                f"Fastest driver changed. "
                f"At {timestamp}, fastest driver is {data.get('fastest_driver')} "
                f"with speed {data.get('fastest_speed')} km/h."
            )

        elif event_type == "LAP_CHANGED":
            return (
                f"Lap changed. "
                f"Driver {data.get('driver')} moved from lap {data.get('from')} "
                f"to lap {data.get('to')} at circuit {data.get('circuit')}."
            )

        elif event_type == "ACCIDENT_DETECTED":
            return (
                f"Accident detected. "
                f"Driver {data.get('driver')} had accident at circuit {data.get('circuit')} "
                f"lap {data.get('lap')} sector {data.get('sector')}."
            )

        elif event_type == "WINNER_DECIDED":
            return (
                f"Race finished. "
                f"Winner is {data.get('winner')} at circuit {data.get('circuit')} "
                f"after {data.get('race_laps')} race laps."
            )

        else:
            return f"Event {event_type} at {timestamp}. Details: {data}"

    except Exception:
        return event_line