import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import paho.mqtt.client as mqtt

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,client_id = "test-publisher")
client.connect("localhost", 1883)
client.loop_start()


def publish(topic, event, label):
    payload = json.dumps(event)
    client.publish(topic, payload)
    print(f"[{label}] {topic}: {payload}")
    time.sleep(2)


# 1. Fall + recovery
publish("home/fall-detection/events", {"event": "fall", "fall": True, "human": True, "room": "living_room"}, "FALL")
publish("home/fall-detection/events", {"event": "state_change", "fall": False, "human": True, "room": "living_room"}, "RECOVERY")

# 2. Fall + escalation
publish("home/fall-detection/events", {"event": "fall", "fall": True, "human": True, "room": "living_room"}, "FALL")
time.sleep(5)
publish("home/fall-detection/events", {"event": "fall_escalated", "room": "living_room", "reason": "no_recovery"}, "ESCALATION")

# 3. Presence - same value 5 times but only the first should log
for i in range(5):
    publish("home/fall-detection/events", {"event": "presence_changed", "human": True, "room": "living_room"}, f"PRESENCE {i+1}")
publish("home/fall-detection/events", {"event": "presence_changed", "human": False, "room": "living_room"}, "PRESENCE CHANGE")

# 4. Radar failure
publish("home/fall-detection/events", {"event": "radar_failure", "room": "living_room"}, "RADAR FAILURE")

# 5. Heartbeat
publish("home/fall-detection/heartbeat", {"device_id": "xiao-fall-detector", "status": "alive"}, "HEARTBEAT")

# 6. Last Will (simulate ESP32 crash)
publish("home/fall-detection/status", {"status": "offline"}, "LAST WILL")

time.sleep(1)
client.loop_stop()
client.disconnect()
print("done")