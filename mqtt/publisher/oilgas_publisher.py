import time
import random
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883

SITES = ["site1", "site2"]
EQUIPMENT = ["pump1", "pump2", "compressor1", "valve1"]
METRICS = ["pressure", "temperature", "flow_rate", "vibration", "status"]


def generate_value(metric):
    if metric == "pressure":
        return round(random.uniform(70, 140), 2)
    if metric == "temperature":
        return round(random.uniform(40, 110), 2)
    if metric == "flow_rate":
        return round(random.uniform(15, 90), 2)
    if metric == "vibration":
        return round(random.uniform(1, 10), 2)
    if metric == "status":
        return random.choice(["running", "idle", "fault"])
    return 0


def main():
    client = mqtt.Client()
    client.connect(BROKER, PORT, 60)

    print("Oilgas publisher running...")

    while True:
        for site in SITES:
            for equipment in EQUIPMENT:
                for metric in METRICS:
                    topic = f"oilgas/{site}/{equipment}/{metric}"
                    value = generate_value(metric)
                    client.publish(topic, str(value))
                    print(f"Published {topic} -> {value}")

        time.sleep(2)


if __name__ == "__main__":
    main()