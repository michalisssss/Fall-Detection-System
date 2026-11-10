import time
import json
import paho.mqtt.client as mqtt

# Connect to the MQTT broker
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="test-multi-room")
client.connect("localhost", 1883)
client.loop_start()

def publish(topic, event, label):
    payload = json.dumps(event)
    result = client.publish(topic, payload)
    if result.rc == 0:
        print(f"[{label}] {topic}: {payload}")
    else:
        print(f"[ERROR] {label}: publish failed (rc={result.rc})")
    time.sleep(2)

print("Multi-room test")
print("Publishing fall events from different rooms...\n")

# 1. Fall in bathroom
publish("home/fall-detection/bathroom/events", {"event": "fall", "fall": True, "human": True, "room": "bathroom"}, "BATHROOM FALL")

# 2. Fall in kitchen
publish("home/fall-detection/kitchen/events", {"event": "fall", "fall": True, "human": True, "room": "kitchen"}, "KITCHEN FALL")

# 3. Recovery in bathroom
publish("home/fall-detection/bathroom/events", {"event": "state_change", "fall": False, "human": True, "room": "bathroom"}, "BATHROOM RECOVERY")

# 4. Presence change in kitchen
publish("home/fall-detection/kitchen/events", {"event": "presence_changed", "human": False, "room": "kitchen"}, "KITCHEN PRESENCE")

print("\nDone")

time.sleep(1)
client.loop_stop()
client.disconnect()