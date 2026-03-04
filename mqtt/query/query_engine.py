import time
import paho.mqtt.client as mqtt
from datetime import datetime

BROKER = "localhost"
PORT = 1883

# Cache: latest value per topic + timestamp
topic_cache = {}

def on_connect(client, userdata, flags, rc):
    print("Query Engine connected to MQTT")
    # Pull both raw telemetry + analytics topics
    client.subscribe("f1/#")
    client.subscribe("race/#")

def on_message(client, userdata, msg):
    topic = msg.topic
    value = msg.payload.decode()

    topic_cache[topic] = {
        "value": value,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ---------- Core lookup helpers ----------
def get_latest(topic: str, default=None):
    """Return latest cached record for a topic."""
    return topic_cache.get(topic, default)

def get_latest_value(topic: str, default=None):
    """Return latest value only."""
    rec = topic_cache.get(topic)
    return rec["value"] if rec else default

# ---------- Convenience APIs (what LLM/RAG will call later) ----------
def driver_topic(team: str, driver: str, metric: str):
    return f"f1/{team}/{driver}/{metric}"

def get_driver_metric(team: str, driver: str, metric: str):
    topic = driver_topic(team, driver, metric)
    return {
        "topic": topic,
        "value": get_latest_value(topic),
        "timestamp": get_latest(topic, {}).get("timestamp")
    }

def get_fastest_driver():
    """Uses Pranith's telemetry_processor published topics."""
    return {
        "topic": "race/fastest_driver",
        "value": get_latest_value("race/fastest_driver"),
        "timestamp": get_latest("race/fastest_driver", {}).get("timestamp")
    }

def get_race_leader():
    return {
        "leader_topic": "race/leader_driver",
        "leader": get_latest_value("race/leader_driver"),
        "lap_topic": "race/leader_lap",
        "lap": get_latest_value("race/leader_lap")
    }

def get_team_avg_speed(team: str):
    topic = f"race/team_avg_speed/{team}"
    return {
        "topic": topic,
        "value": get_latest_value(topic),
        "timestamp": get_latest(topic, {}).get("timestamp")
    }

# ---------- Run loop ----------
def start_cache_listener():
    client = mqtt.Client()
    client.reconnect_delay_set(min_delay=1, max_delay=5)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT, 60)
    client.loop_start()
    return client

if __name__ == "__main__":
    # Demo: start listener + print a few lookups repeatedly
    start_cache_listener()

    # Wait a moment for cache to populate
    time.sleep(2)

    while True:
        print("\n--- Query Engine Demo ---")
        print("Hamilton speed:", get_driver_metric("mercedes", "hamilton", "speed"))
        print("Verstappen lap:", get_driver_metric("redbull", "verstappen", "lap"))
        print("Fastest driver:", get_fastest_driver())
        print("Race leader:", get_race_leader())
        print("RedBull avg speed:", get_team_avg_speed("redbull"))
        time.sleep(5)
