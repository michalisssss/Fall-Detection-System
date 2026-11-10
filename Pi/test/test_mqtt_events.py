import time
import json
import paho.mqtt.client as mqtt

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="test-publisher")
client.connect("localhost", 1883)
client.loop_start()

# Define the room for testing (must match ROOM_NAME in ESP32's config.h)
ROOM = "living_room"

# Publish a JSON event to the given MQTT topic and log the result
def publish(topic, event, label):
    # Serialize event dict to a JSON string
    payload = json.dumps(event)

    # Publish and check the return code
    result = client.publish(topic, payload)
    if result.rc == 0: # success
        print(f"[{label}] {topic}: {payload}")
    else: # rc != 0 -> fail
        print(f"[ERROR] {label}: publish failed (rc={result.rc})")

    # Give the broker time to deliver the message before the next event
    time.sleep(2)

# 1. Fall + recovery
# Expected -> fall alert sent, escalation timer started and then cancelled on recovery
publish(f"home/fall-detection/{ROOM}/events", {"event": "fall", "fall": True, "human": True, "room": ROOM}, "FALL")
publish(f"home/fall-detection/{ROOM}/events", {"event": "state_change", "fall": False, "human": True, "room": ROOM}, "RECOVERY")

# 2. Fall + escalation
# Expected -> fall alert sent and then escalation alert after ESCALATION_DELAY_SEC
publish(f"home/fall-detection/{ROOM}/events", {"event": "fall", "fall": True, "human": True, "room": ROOM}, "FALL")
time.sleep(5)
publish(f"home/fall-detection/{ROOM}/events", {"event": "fall_escalated", "room": ROOM, "reason": "no_recovery"}, "ESCALATION")

# 3. Presence - same value 5 times but only the first should log
# Expected -> only 1 presence log for the 5 identical events and then one for the change
for i in range(5):
    publish(f"home/fall-detection/{ROOM}/events", {"event": "presence_changed", "human": True, "room": ROOM}, f"PRESENCE {i+1}")
publish(f"home/fall-detection/{ROOM}/events", {"event": "presence_changed", "human": False, "room": ROOM}, "PRESENCE CHANGE")

# 4. Radar failure
# Expected -> Telegram alert "Radar failure in living_room"
publish(f"home/fall-detection/{ROOM}/events", {"event": "radar_failure", "room": ROOM}, "RADAR FAILURE")

# 5. Heartbeat
# Expected -> no Telegram alert (just received by main.py)
publish(f"home/fall-detection/{ROOM}/heartbeat", {"device_id": f"xiao-{ROOM}", "status": "alive"}, "HEARTBEAT")

# 6. Last Will (simulate ESP32 crash)
# Expected -> Telegram alert "Node disconnected from MQTT"
publish(f"home/fall-detection/{ROOM}/status", {"status": "offline"}, "LAST WILL")

time.sleep(1)
client.loop_stop()
client.disconnect()
print("done")