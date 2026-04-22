import time
import paho.mqtt.client as mqtt
from mqtt.adapters.loader import get_adapter
from mqtt.config import DATASET_ADAPTER

adapter = get_adapter()

BROKER = "localhost"
PORT = 1883

PRINT_EVERY_SECONDS = 5
PUBLISH_ANALYTICS = True

topic_cache = {}


def on_connect(client, userdata, flags, rc):
    print(f"Telemetry Processor connected to MQTT | Dataset: {DATASET_ADAPTER}")
    for topic in adapter.INPUT_TOPICS_PROCESSOR:
        client.subscribe(topic)


def on_message(client, userdata, msg):
    topic_cache[msg.topic] = msg.payload.decode()


def print_generic_analytics(analytics: dict):
    print("\n===== LIVE ANALYTICS =====")

    if not analytics:
        print("No analytics available.")
        return

    for key, value in analytics.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for sub_key, sub_value in value.items():
                print(f"  {sub_key} -> {sub_value}")
        else:
            print(f"{key}: {value}")


def main():
    client = mqtt.Client()
    client.reconnect_delay_set(min_delay=1, max_delay=5)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)

    client.loop_start()

    while True:
        time.sleep(PRINT_EVERY_SECONDS)

        analytics = adapter.compute_analytics_from_cache(topic_cache)
        if not analytics:
            print("Waiting for telemetry...")
            continue

        print_generic_analytics(analytics)

        if PUBLISH_ANALYTICS:
            adapter.publish_analytics(client, analytics)


if __name__ == "__main__":
    main()