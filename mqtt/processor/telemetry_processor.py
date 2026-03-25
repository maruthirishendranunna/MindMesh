import time
import paho.mqtt.client as mqtt
from mqtt.adapters.loader import get_adapter

adapter = get_adapter()

BROKER = "localhost"
PORT = 1883

PRINT_EVERY_SECONDS = 5
PUBLISH_ANALYTICS = True

topic_cache = {}


def on_connect(client, userdata, flags, rc):
    print("Telemetry Processor connected to MQTT")
    for topic in adapter.INPUT_TOPICS_PROCESSOR:
        client.subscribe(topic)


def on_message(client, userdata, msg):
    topic_cache[msg.topic] = msg.payload.decode()


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

        fastest_driver = analytics["fastest_driver"]
        fastest_speed = analytics["fastest_speed"]
        fastest_circuit = analytics["fastest_circuit"]
        leader = analytics["leader"]
        leader_lap = analytics["leader_lap"]
        leader_circuit = analytics["leader_circuit"]
        team_avg = analytics["team_avg"]

        print("\n===== LIVE ANALYTICS =====")
        print(f"Fastest Driver: {fastest_driver} | Speed: {round(fastest_speed, 2)} | Circuit: {fastest_circuit}")
        print(f"Race Leader:    {leader} | Lap: {leader_lap} | Circuit: {leader_circuit}")
        print("Team Avg Speeds:")
        for team, avg in team_avg.items():
            print(f"  {team} -> {round(avg, 2)}")

        if PUBLISH_ANALYTICS:
            adapter.publish_analytics(client, analytics)


if __name__ == "__main__":
    main()