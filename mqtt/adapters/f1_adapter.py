import os
import json
from collections import defaultdict

# =========================
# DATASET-SPECIFIC CONFIG
# =========================

INPUT_TOPICS_PROCESSOR = ["f1/#"]
INPUT_TOPICS_SNAPSHOTTER = ["f1/#", "race/#"]
ANALYTICS_PREFIX = "race"

# Final chunking strategy for this dataset
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

    # Race leader changed
    leader_driver = analytics.get("leader_driver", {}).get("value")
    leader_lap = analytics.get("leader_lap", {}).get("value")
    leader_tuple = (leader_driver, leader_lap)

    if leader_driver and leader_tuple != last_seen["race_leader"]:
        log_event_callback("RACE_LEADER_CHANGED", {
            "leader": leader_driver,
            "lap": leader_lap
        })
        last_seen["race_leader"] = leader_tuple

    # Fastest driver changed
    fastest_driver = analytics.get("fastest_driver", {}).get("value")
    fastest_speed = analytics.get("fastest_speed", {}).get("value")
    fastest_tuple = (fastest_driver, fastest_speed)

    if fastest_driver and fastest_tuple != last_seen["fastest"]:
        log_event_callback("FASTEST_DRIVER_CHANGED", {
            "fastest_driver": fastest_driver,
            "fastest_speed": fastest_speed
        })
        last_seen["fastest"] = fastest_tuple

    # Per-driver events
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
                    log_event_callback("LAP_CHANGED", {
                        "driver": key,
                        "from": prev_lap,
                        "to": lap_val,
                        "circuit": circuit
                    })
                    last_seen["driver_laps"][key] = lap_val

            # Accident detected
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

            # Winner decided
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
    """
    Improved semantic formatting for better retrieval.
    Bhavana Week-4 task.
    """
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
    """
    Improved semantic formatting for event retrieval.
    Bhavana Week-4 task.
    """
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