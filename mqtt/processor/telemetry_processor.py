import time
from collections import defaultdict
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883

PRINT_EVERY_SECONDS = 5
PUBLISH_ANALYTICS = True   # set False if you only want console output

# local cache inside this processor (NOT shared memory)
topic_cache = {}

def safe_float(x):
    try:
        return float(x)
    except:
        return None

def safe_int(x):
    try:
        return int(float(x))
    except:
        return None

def parse_topic(topic: str):
    # f1/<team>/<driver>/<metric>
    parts = topic.split("/")
    if len(parts) != 4:
        return None
    if parts[0] != "f1":
        return None
    return parts[1], parts[2], parts[3]

def on_connect(client, userdata, flags, rc):
    print("Telemetry Processor connected to MQTT")
    client.subscribe("f1/#")

def on_message(client, userdata, msg):
    # store latest value
    topic_cache[msg.topic] = msg.payload.decode()

def build_driver_map():
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

def compute_fastest_driver(drivers):
    fastest_driver = None
    fastest_speed = -1.0
    fastest_circuit = None

    for d, m in drivers.items():
        sp = safe_float(m.get("speed"))
        if sp is None:
            continue
        if sp > fastest_speed:
            fastest_speed = sp
            fastest_driver = d
            fastest_circuit = m.get("circuit")
    return fastest_driver, fastest_speed, fastest_circuit

def compute_leader(drivers):
    leader = None
    leader_lap = -1
    leader_circuit = None

    for d, m in drivers.items():
        lap = safe_int(m.get("lap"))
        if lap is None:
            continue
        if lap > leader_lap:
            leader_lap = lap
            leader = d
            leader_circuit = m.get("circuit")
    return leader, leader_lap, leader_circuit

def compute_team_avg_speed(drivers):
    team_speeds = defaultdict(list)
    for d, m in drivers.items():
        team = d.split("/")[0]
        sp = safe_float(m.get("speed"))
        if sp is None:
            continue
        team_speeds[team].append(sp)

    team_avg = {}
    for team, speeds in team_speeds.items():
        if speeds:
            team_avg[team] = sum(speeds) / len(speeds)
    return team_avg

def publish(client, topic, value):
    client.publish(topic, str(value), qos=0, retain=False)

def main():
    client = mqtt.Client()
    client.reconnect_delay_set(min_delay=1, max_delay=5)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)

    # Run MQTT network loop in background thread
    client.loop_start()

    while True:
        time.sleep(PRINT_EVERY_SECONDS)

        drivers = build_driver_map()
        if not drivers:
            print("Waiting for telemetry...")
            continue

        fastest_driver, fastest_speed, fastest_circuit = compute_fastest_driver(drivers)
        leader, leader_lap, leader_circuit = compute_leader(drivers)
        team_avg = compute_team_avg_speed(drivers)

        print("\n===== LIVE ANALYTICS =====")
        print(f"Fastest Driver: {fastest_driver} | Speed: {round(fastest_speed, 2)} | Circuit: {fastest_circuit}")
        print(f"Race Leader:    {leader} | Lap: {leader_lap} | Circuit: {leader_circuit}")
        print("Team Avg Speeds:")
        for team, avg in team_avg.items():
            print(f"  {team} -> {round(avg, 2)}")

        if PUBLISH_ANALYTICS:
            publish(client, "race/fastest_driver", fastest_driver or "unknown")
            publish(client, "race/fastest_speed", round(fastest_speed, 2) if fastest_speed >= 0 else "unknown")
            publish(client, "race/leader_driver", leader or "unknown")
            publish(client, "race/leader_lap", leader_lap if leader_lap >= 0 else "unknown")

            for team, avg in team_avg.items():
                publish(client, f"race/team_avg_speed/{team}", round(avg, 2))

            # optional circuit-specific topics
            if fastest_circuit and fastest_driver:
                publish(client, f"race/{fastest_circuit}/fastest_driver", fastest_driver)
                publish(client, f"race/{fastest_circuit}/fastest_speed", round(fastest_speed, 2))

            if leader_circuit and leader:
                publish(client, f"race/{leader_circuit}/leader_driver", leader)
                publish(client, f"race/{leader_circuit}/leader_lap", leader_lap)

if __name__ == "__main__":
    main()
