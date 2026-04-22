import importlib
from mqtt.config import DATASET_ADAPTER

REQUIRED_ADAPTER_ATTRIBUTES = [
    "INPUT_TOPICS_PROCESSOR",
    "INPUT_TOPICS_SNAPSHOTTER",
    "ANALYTICS_PREFIX",
    "SNAPSHOTS_PER_CHUNK",
    "EVENTS_PER_CHUNK",
    "init_last_seen",
    "normalize_question_text",
    "parse_topic",
    "extract_entities",
    "classify_query",
    "compute_analytics_from_cache",
    "publish_analytics",
    "build_snapshot_from_cache",
    "detect_events",
    "format_snapshot_to_text",
    "format_event_line",
    "filter_telemetry_lines",
    "build_telemetry_query_from_topics",
    "can_handle_directly",
    "get_direct_answer",
]


def get_adapter():
    module_name = f"mqtt.adapters.{DATASET_ADAPTER}"
    adapter = importlib.import_module(module_name)

    missing = []
    for attr in REQUIRED_ADAPTER_ATTRIBUTES:
        if not hasattr(adapter, attr):
            missing.append(attr)

    if missing:
        raise AttributeError(
            f"Adapter '{DATASET_ADAPTER}' is missing required attributes/functions: {missing}"
        )

    return adapter