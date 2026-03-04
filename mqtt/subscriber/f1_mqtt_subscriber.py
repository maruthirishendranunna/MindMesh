import paho.mqtt.client as mqtt
from datetime import datetime

# Real-time topic cache
topic_cache = {}

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT")
    client.subscribe("f1/#")   # subscribe to all telemetry topics

def on_message(client, userdata, msg):
    topic = msg.topic
    value = msg.payload.decode()

    # Store latest value with timestamp in cache
    topic_cache[topic] = {
        "value": value,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Week 1: just verify live data
    print(f"{topic} -> {value}")

def get_latest_value(topic):
    """
    Helper function for future RAG/backend use.
    Returns latest cached value for a topic.
    """
    return topic_cache.get(topic, None)

client = mqtt.Client()
client.reconnect_delay_set(min_delay=1, max_delay=5)
client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883, 60)
client.loop_forever()
