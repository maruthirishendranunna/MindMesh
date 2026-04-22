import json
import re


INPUT_TOPICS_PROCESSOR = ["oilgas/#"]
INPUT_TOPICS_SNAPSHOTTER = ["oilgas/#", "oilgas_analytics/#"]
ANALYTICS_PREFIX = "oilgas_analytics"

SNAPSHOTS_PER_CHUNK = 5
EVENTS_PER_CHUNK = 10

TOP_K_TOPIC = 2
TOP_K_TELEMETRY = 8
TOP_K_FALLBACK = 10
SEARCH_TOP_K = 5
SEARCH_FINAL_TOP_K = 3


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def normalize_question_text(question: str) -> str:
    q = question.lower().strip()

    replacements = {
        "temprature": "temperature",
        "presure": "pressure",
        "flowrate": "flow_rate",
        "flow rate": "flow_rate",
        "temp": "temperature",
        "state": "status",
    }

    for wrong, correct in replacements.items():
        q = q.replace(wrong, correct)

    return q


def parse_topic(topic: str):
    parts = topic.split("/")
    if len(parts) != 4:
        return None

    if parts[0] != "oilgas":
        return None

    return parts[1], parts[2], parts[3]


def extract_entities(question: str) -> dict:
    q = normalize_question_text(question)

    entities = {
        "site": None,
        "equipment": None,
        "metric": None
    }

    known_sites = [
        "site1",
        "site2",
        "site3"
    ]

    known_equipment = [
        "pump1",
        "pump2",
        "pump3",
        "valve1",
        "valve2",
        "valve3",
        "compressor1",
        "compressor2",
        "tank1",
        "tank2"
    ]

    metric_aliases = {
        "pressure": "pressure",
        "temperature": "temperature",
        "flow_rate": "flow_rate",
        "flow": "flow_rate",
        "vibration": "vibration",
        "status": "status",
    }

    for site in known_sites:
        if site in q:
            entities["site"] = site
            break

    for eq in known_equipment:
        if eq in q:
            entities["equipment"] = eq
            break

    ordered_metric_keys = [
        "flow_rate",
        "temperature",
        "pressure",
        "vibration",
        "status",
        "flow",
    ]

    for key in ordered_metric_keys:
        if key in q:
            entities["metric"] = metric_aliases[key]
            break

    return entities


def classify_query(question: str) -> str:
    q = normalize_question_text(question)

    if any(x in q for x in [
        "fault", "alert", "abnormal",
        "high pressure", "high temperature",
        "high vibration", "status changed"
    ]):
        return "event"

    if any(x in q for x in [
        "highest", "lowest", "max", "min",
        "top", "best", "maximum", "minimum"
    ]):
        return "comparison"

    return "metric"


def init_last_seen():
    return {
        "high_pressure": {},
        "high_temperature": {},
        "high_vibration": {},
        "status": {}
    }


def compute_analytics_from_cache(topic_cache: dict):
    highest_pressure = None
    highest_pressure_site = None
    highest_pressure_equipment = None

    for topic, value in topic_cache.items():
        parsed = parse_topic(topic)
        if not parsed:
            continue

        site, equipment, metric = parsed
        if metric != "pressure":
            continue

        p = safe_float(value)
        if p is None:
            continue

        if highest_pressure is None or p > highest_pressure:
            highest_pressure = p
            highest_pressure_site = site
            highest_pressure_equipment = equipment

    result = {}
    if highest_pressure is not None:
        result["highest_pressure"] = highest_pressure
        result["highest_pressure_site"] = highest_pressure_site
        result["highest_pressure_equipment"] = highest_pressure_equipment

    return result


def publish_analytics(client, analytics: dict):
    for key, value in analytics.items():
        client.publish(f"{ANALYTICS_PREFIX}/{key}", str(value))


def build_snapshot_from_cache(topic_cache: dict, snapshot_time: str):
    snapshot = {
        "snapshot_time": snapshot_time,
        "telemetry": {},
        "analytics": {}
    }

    for topic, record in topic_cache.items():
        parts = topic.split("/")

        if parts[0] == "oilgas" and len(parts) >= 4:
            site = parts[1]
            equipment = parts[2]
            metric = parts[3]

            snapshot["telemetry"].setdefault(site, {})
            snapshot["telemetry"][site].setdefault(equipment, {})
            snapshot["telemetry"][site][equipment][metric] = record

        elif parts[0] == ANALYTICS_PREFIX:
            metric = "/".join(parts[1:])
            snapshot["analytics"][metric] = record

    return snapshot


def detect_events(snapshot: dict, last_seen: dict, log_event_callback):
    telemetry = snapshot.get("telemetry", {})

    for site, equipment_map in telemetry.items():
        for equipment, metrics in equipment_map.items():
            key = f"{site}/{equipment}"

            pressure = safe_float(metrics.get("pressure", {}).get("value"))
            temperature = safe_float(metrics.get("temperature", {}).get("value"))
            vibration = safe_float(metrics.get("vibration", {}).get("value"))
            status = str(metrics.get("status", {}).get("value", "")).lower()

            if pressure is not None and pressure > 120:
                if not last_seen["high_pressure"].get(key):
                    log_event_callback("HIGH_PRESSURE", {
                        "site": site,
                        "equipment": equipment,
                        "pressure": pressure
                    })
                    last_seen["high_pressure"][key] = True
            else:
                last_seen["high_pressure"][key] = False

            if temperature is not None and temperature > 90:
                if not last_seen["high_temperature"].get(key):
                    log_event_callback("HIGH_TEMPERATURE", {
                        "site": site,
                        "equipment": equipment,
                        "temperature": temperature
                    })
                    last_seen["high_temperature"][key] = True
            else:
                last_seen["high_temperature"][key] = False

            if vibration is not None and vibration > 8:
                if not last_seen["high_vibration"].get(key):
                    log_event_callback("HIGH_VIBRATION", {
                        "site": site,
                        "equipment": equipment,
                        "vibration": vibration
                    })
                    last_seen["high_vibration"][key] = True
            else:
                last_seen["high_vibration"][key] = False

            prev_status = last_seen["status"].get(key)
            if prev_status is None:
                last_seen["status"][key] = status
            elif prev_status != status:
                log_event_callback("STATUS_CHANGED", {
                    "site": site,
                    "equipment": equipment,
                    "old_status": prev_status,
                    "new_status": status
                })
                last_seen["status"][key] = status


def format_snapshot_to_text(snapshot: dict) -> str:
    lines = []

    snap_time = snapshot.get("snapshot_time", "unknown")
    lines.append(f"Snapshot time: {snap_time}.")

    telemetry = snapshot.get("telemetry", {})

    for site, equipment_map in telemetry.items():
        for equipment, metrics in equipment_map.items():
            pressure = metrics.get("pressure", {}).get("value", "unknown")
            temperature = metrics.get("temperature", {}).get("value", "unknown")
            flow_rate = metrics.get("flow_rate", {}).get("value", "unknown")
            vibration = metrics.get("vibration", {}).get("value", "unknown")
            status = metrics.get("status", {}).get("value", "unknown")

            lines.append(
                f"Equipment {equipment} at site {site}. "
                f"Pressure is {pressure} psi. "
                f"Temperature is {temperature} C. "
                f"Flow rate is {flow_rate} lpm. "
                f"Vibration is {vibration} mm/s. "
                f"Status is {status}."
            )

    return "\n".join(lines)


def format_event_line(event_line: str) -> str:
    try:
        event = json.loads(event_line)
        timestamp = event.get("timestamp", "unknown")
        event_type = event.get("type", "UNKNOWN")
        data = event.get("data", {})
        return f"Event {event_type} at {timestamp}: {data}"
    except Exception:
        return event_line


def filter_telemetry_lines(original_question: str, refined_question: str, text: str):
    q = normalize_question_text(original_question)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    entities = extract_entities(q)
    site = entities.get("site")
    equipment = entities.get("equipment")
    metric = entities.get("metric")

    filtered = []
    for line in lines:
        ll = line.lower()

        if site and site not in ll:
            continue
        if equipment and equipment not in ll:
            continue

        if metric:
            if metric == "flow_rate" and "flow rate" not in ll:
                continue
            if metric == "pressure" and "pressure" not in ll:
                continue
            if metric == "temperature" and "temperature" not in ll:
                continue
            if metric == "vibration" and "vibration" not in ll:
                continue
            # no strict "status" filter on purpose

        filtered.append(line)

    return filtered if filtered else lines[:8]


def build_telemetry_query_from_topics(original_question: str, topic_docs):
    q = normalize_question_text(original_question)
    entities = extract_entities(q)

    parts = []
    if entities["site"]:
        parts.append(entities["site"])
    if entities["equipment"]:
        parts.append(entities["equipment"])
    if entities["metric"]:
        parts.append(entities["metric"])

    if topic_docs:
        first_topic = topic_docs[0].metadata.get("topic", "")
        if first_topic:
            parts.append(first_topic)

    return " ".join(parts).strip() or q


def can_handle_directly(question: str) -> bool:
    q = normalize_question_text(question)

    followup_patterns = [
        "what about other",
        "what about others",
        "what about the rest",
        "show others",
        "show the rest",
        "and the rest",
    ]

    if any(p in q for p in followup_patterns):
        return True

    deterministic_keywords = [
        "pressure",
        "temperature",
        "flow_rate",
        "flow",
        "vibration",
        "status",
        "highest",
        "lowest",
        "maximum",
        "minimum",
        "max",
        "min",
        "top",
        "best",
        "fault",
        "alert",
        "abnormal",
        "high pressure",
        "high temperature",
        "high vibration",
        "status changed",
    ]

    return any(k in q for k in deterministic_keywords)


def get_direct_answer(question: str, context: str):
    q = normalize_question_text(question)
    entities = extract_entities(q)

    site = entities.get("site")
    equipment = entities.get("equipment")
    metric = entities.get("metric")

    if "what about other" in q or "what about others" in q or "what about the rest" in q:
        lines = [line.strip() for line in context.splitlines() if line.strip()]
        relevant = [
            line for line in lines
            if line.lower().startswith("equipment ")
        ]

        if not relevant:
            return "No other relevant data found."

        results = []
        for line in relevant[:5]:
            results.append(line)

        return "Other relevant equipment data:\n- " + "\n- ".join(results)

    lines = [line.strip() for line in context.splitlines() if line.strip()]
    relevant = [
        line for line in lines
        if line.lower().startswith("equipment ")
    ]

    if not relevant:
        return None

    filtered = []
    for line in relevant:
        ll = line.lower()

        if site and site not in ll:
            continue

        if equipment:
            eq_match = re.search(r"equipment (\w+)", ll)
            if not eq_match or eq_match.group(1) != equipment:
                continue

        filtered.append(line)

    if not filtered:
        return None

    if site and not equipment:
        seen_equipment = set()
        results = []

        for line in filtered:
            eq_match = re.search(r"equipment (\w+)", line, re.IGNORECASE)
            eq_name = eq_match.group(1) if eq_match else "equipment"

            if eq_name in seen_equipment:
                continue

            if metric == "flow_rate":
                m = re.search(r"Flow rate is ([0-9.]+) lpm", line, re.IGNORECASE)
                if m:
                    seen_equipment.add(eq_name)
                    results.append(f"{eq_name}: {m.group(1)} lpm")

            elif metric == "pressure":
                m = re.search(r"Pressure is ([0-9.]+) psi", line, re.IGNORECASE)
                if m:
                    seen_equipment.add(eq_name)
                    results.append(f"{eq_name}: {m.group(1)} psi")

            elif metric == "temperature":
                m = re.search(r"Temperature is ([0-9.]+) C", line, re.IGNORECASE)
                if m:
                    seen_equipment.add(eq_name)
                    results.append(f"{eq_name}: {m.group(1)} C")

            elif metric == "vibration":
                m = re.search(r"Vibration is ([0-9.]+) mm/s", line, re.IGNORECASE)
                if m:
                    seen_equipment.add(eq_name)
                    results.append(f"{eq_name}: {m.group(1)} mm/s")

            elif metric == "status":
                m = re.search(r"Status is ([a-zA-Z0-9_]+)", line, re.IGNORECASE)
                if m:
                    seen_equipment.add(eq_name)
                    results.append(f"{eq_name}: {m.group(1)}")

        if results:
            results = sorted(results)
            return f"{metric.replace('_', ' ')} at {site}:\n- " + "\n- ".join(results[:10])

    chosen = filtered[0]

    chosen_site_match = re.search(r"site (\w+)", chosen, re.IGNORECASE)
    chosen_site = chosen_site_match.group(1) if chosen_site_match else (site if site else "site")

    chosen_eq_match = re.search(r"equipment (\w+)", chosen, re.IGNORECASE)
    chosen_equipment = chosen_eq_match.group(1) if chosen_eq_match else (equipment if equipment else "equipment")

    if metric == "pressure":
        m = re.search(r"Pressure is ([0-9.]+) psi", chosen, re.IGNORECASE)
        if m:
            return f"{chosen_equipment} pressure at {chosen_site} is {m.group(1)} psi."
        return chosen

    if metric == "temperature":
        m = re.search(r"Temperature is ([0-9.]+) C", chosen, re.IGNORECASE)
        if m:
            return f"{chosen_equipment} temperature at {chosen_site} is {m.group(1)} C."
        return chosen

    if metric == "flow_rate":
        m = re.search(r"Flow rate is ([0-9.]+) lpm", chosen, re.IGNORECASE)
        if m:
            return f"{chosen_equipment} flow rate at {chosen_site} is {m.group(1)} lpm."
        return chosen

    if metric == "vibration":
        m = re.search(r"Vibration is ([0-9.]+) mm/s", chosen, re.IGNORECASE)
        if m:
            return f"{chosen_equipment} vibration at {chosen_site} is {m.group(1)} mm/s."
        return chosen

    if metric == "status":
        m = re.search(r"Status is ([a-zA-Z0-9_]+)", chosen, re.IGNORECASE)
        if m:
            return f"{chosen_equipment} status at {chosen_site} is {m.group(1)}."
        return chosen

    return chosen