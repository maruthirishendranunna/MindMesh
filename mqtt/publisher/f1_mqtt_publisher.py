import time
import random
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
PUBLISH_HZ = 1

ROTATE_EVERY_SECONDS = 120  # rotate circuit every 2 minutes (Option A)

teams = {
    "redbull": ["verstappen", "perez"],
    "mercedes": ["hamilton", "russell"],
    "mclaren": ["norris", "piastri"],
    "astonmartin": ["alonso", "stroll"],
}

circuits = [
    {"name": "Monza", "lap_km": 5.793, "race_laps": 53, "drs_zones": [(0.12, 0.18), (0.55, 0.62)]},
    {"name": "Silverstone", "lap_km": 5.891, "race_laps": 52, "drs_zones": [(0.08, 0.14), (0.68, 0.74)]},
    {"name": "Spa-Francorchamps", "lap_km": 7.004, "race_laps": 44, "drs_zones": [(0.20, 0.26), (0.63, 0.70)]},
    {"name": "Bahrain", "lap_km": 5.412, "race_laps": 57, "drs_zones": [(0.10, 0.16), (0.48, 0.54), (0.72, 0.78)]},
]

GEAR_SPEED_RANGES = {
    1: (0, 80),
    2: (50, 120),
    3: (90, 160),
    4: (130, 220),
    5: (180, 260),
    6: (220, 300),
    7: (260, 330),
    8: (300, 350),
}

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def in_any_zone(progress, zones):
    return any(a <= progress <= b for a, b in zones)

def pick_sector(progress):
    if progress < 1/3:
        return 1
    elif progress < 2/3:
        return 2
    return 3

def init_driver_state(circuit):
    return {
        "circuit": circuit["name"],
        "lap_km": circuit["lap_km"],
        "race_laps": circuit["race_laps"],
        "drs_zones": circuit["drs_zones"],

        "lap": 1,
        "lap_progress": random.uniform(0.0, 0.2),

        "gear": 3,
        "speed": 120.0,
        "rpm": 9000.0,
        "engine_temp": random.uniform(85, 95),
        "fuel_level": random.uniform(60, 110),

        "drs": 0,
        "accident": 0,
        "accident_ticks_left": 0,

        # NEW: save per-circuit progress so we can resume later
        "saved_progress": {}  # { circuit_name: {"lap": int, "lap_progress": float} }
    }

def switch_to_circuit(st, new_circuit):
    """Save current circuit lap state, then switch and restore state for the new circuit."""
    # Save current circuit state
    current = st["circuit"]
    st["saved_progress"][current] = {
        "lap": st["lap"],
        "lap_progress": st["lap_progress"],
    }

    # Switch circuit metadata
    st["circuit"] = new_circuit["name"]
    st["lap_km"] = new_circuit["lap_km"]
    st["race_laps"] = new_circuit["race_laps"]
    st["drs_zones"] = new_circuit["drs_zones"]

    # Restore if previously seen, else start at lap 1
    if st["circuit"] in st["saved_progress"]:
        st["lap"] = st["saved_progress"][st["circuit"]]["lap"]
        st["lap_progress"] = st["saved_progress"][st["circuit"]]["lap_progress"]
    else:
        st["lap"] = 1
        st["lap_progress"] = 0.0

    # Reset event flags only (not lap)
    st["drs"] = 0
    st["accident"] = 0
    st["accident_ticks_left"] = 0

def update_state(st):
    # Accident behavior
    if st["accident_ticks_left"] > 0:
        st["accident"] = 1
        st["accident_ticks_left"] -= 1
        st["speed"] = max(0.0, st["speed"] - random.uniform(40, 80))
        st["gear"] = 1 if st["speed"] < 20 else 2
        st["rpm"] = clamp(2000 + st["speed"] * 50, 1500, 6000)
        st["drs"] = 0
        return
    else:
        st["accident"] = 0

    # Trigger accident occasionally
    if random.random() < 0.002:
        st["accident_ticks_left"] = random.randint(5, 12)
        return

    # Random shifting
    if random.random() < 0.15:
        st["gear"] = clamp(st["gear"] + random.choice([-1, 1]), 1, 8)

    # Speed depends on gear
    lo, hi = GEAR_SPEED_RANGES[st["gear"]]
    target_speed = random.uniform(lo, hi)
    st["speed"] += (target_speed - st["speed"]) * random.uniform(0.15, 0.35)
    st["speed"] = clamp(st["speed"], 0, 350)

    # RPM derived from speed + gear
    base = 2500 + st["speed"] * 35
    gear_factor = 1.15 - (st["gear"] * 0.08)
    st["rpm"] = clamp(base * gear_factor, 3000, 15000)

    # Engine temp drift
    st["engine_temp"] += random.uniform(-0.3, 0.5) + (st["rpm"] - 9000) * 0.00002
    st["engine_temp"] = clamp(st["engine_temp"], 80, 120)

    # Fuel decreases slowly
    st["fuel_level"] -= random.uniform(0.01, 0.05)
    st["fuel_level"] = clamp(st["fuel_level"], 0, 110)

    # Lap progress based on speed
    km_per_tick = st["speed"] / 3600.0
    st["lap_progress"] += km_per_tick / st["lap_km"]

    if st["lap_progress"] >= 1.0:
        st["lap_progress"] -= 1.0
        st["lap"] += 1
        # if lap exceeds race_laps, keep it capped (demo safety)
        if st["lap"] > st["race_laps"]:
            st["lap"] = st["race_laps"]

    # DRS logic
    in_zone = in_any_zone(st["lap_progress"], st["drs_zones"])
    if in_zone and st["speed"] > 180 and random.random() < 0.6:
        st["drs"] = 1
        st["speed"] = clamp(st["speed"] + random.uniform(2, 8), 0, 350)
    else:
        st["drs"] = 0

def publish(client, team, driver, metric, value):
    topic = f"f1/{team}/{driver}/{metric}"
    client.publish(topic, str(value))

def main():
    client = mqtt.Client()
    client.connect(BROKER, PORT, 60)

    # Round-robin circuit order (not random)
    circuit_index = 0
    chosen = circuits[circuit_index]

    states = {(team, driver): init_driver_state(chosen)
              for team, drivers in teams.items()
              for driver in drivers}

    next_rotate_time = time.time() + ROTATE_EVERY_SECONDS

    print(f"Publishing F1 telemetry | Starting circuit: {chosen['name']} | rotates every {ROTATE_EVERY_SECONDS}s")
    print("Circuit order: Monza -> Silverstone -> Spa-Francorchamps -> Bahrain -> repeat\n")

    tick_sleep = 1.0 / PUBLISH_HZ

    while True:
        now = time.time()

        # Rotate circuit every 2 minutes, round-robin, resume per-circuit lap state
        if now >= next_rotate_time:
            circuit_index = (circuit_index + 1) % len(circuits)
            chosen = circuits[circuit_index]

            for st in states.values():
                switch_to_circuit(st, chosen)

            next_rotate_time = now + ROTATE_EVERY_SECONDS
            print(f"\n=== Circuit switched to {chosen['name']} | Race laps: {chosen['race_laps']} (resuming if seen before) ===\n")

        for (team, driver), st in states.items():
            update_state(st)

            sector = pick_sector(st["lap_progress"])
            lap_remaining = max(0, st["race_laps"] - st["lap"])

            publish(client, team, driver, "circuit", st["circuit"])
            publish(client, team, driver, "race_laps", int(st["race_laps"]))
            publish(client, team, driver, "lap", int(st["lap"]))
            publish(client, team, driver, "lap_remaining", int(lap_remaining))
            publish(client, team, driver, "sector", int(sector))

            publish(client, team, driver, "speed", round(st["speed"], 2))
            publish(client, team, driver, "rpm", round(st["rpm"], 2))
            publish(client, team, driver, "gear", int(st["gear"]))
            publish(client, team, driver, "engine_temp", round(st["engine_temp"], 2))
            publish(client, team, driver, "fuel_level", round(st["fuel_level"], 2))

            publish(client, team, driver, "drs", int(st["drs"]))
            publish(client, team, driver, "accident", int(st["accident"]))

            print(
                f"{team}/{driver} | {st['circuit']} lap {st['lap']}/{st['race_laps']} s{sector} | "
                f"g{st['gear']} {st['speed']:.1f}kmh rpm{st['rpm']:.0f} drs{st['drs']} acc{st['accident']}"
            )

        time.sleep(tick_sleep)

if __name__ == "__main__":
    main()
