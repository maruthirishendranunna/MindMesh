import time
import random
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883

teams = {
    "redbull": ["verstappen", "perez"],
    "mercedes": ["hamilton", "russell"],
    "mclaren": ["norris", "piastri"],
    "astonmartin": ["alonso", "stroll"],
}

metrics = {
    "speed": (0, 350),
    "rpm": (3000, 15000),
    "gear": (1, 8),
    "engine_temp": (80, 120),
    "fuel_level": (0, 110),
}

client = mqtt.Client()
client.connect(BROKER, PORT, 60)

print("Publishing F1 telemetry (teams + drivers)...")

while True:
    for team, drivers in teams.items():
        for driver in drivers:
            for metric, (low, high) in metrics.items():
                value = random.randint(low, high) if metric == "gear" else round(random.uniform(low, high), 2)
                topic = f"f1/{team}/{driver}/{metric}"
                client.publish(topic, value)
                print(f"{topic} -> {value}")
    time.sleep(1)