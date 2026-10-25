import time
import json
import paho.mqtt.client as mqtt

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="test-publisher")
client.connect("localhost", 1883)
client.loop_start()

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
publish("home/fall-detection/events", {"event": "fall", "fall": True, "human": True, "room": "living_room"}, "FALL")
publish("home/fall-detection/events", {"event": "state_change", "fall": False, "human": True, "room": "living_room"}, "RECOVERY")

# 2. Fall + escalation
# Expected -> fall alert sent and then escalation alert after ESCALATION_DELAY_SEC
publish("home/fall-detection/events", {"event": "fall", "fall": True, "human": True, "room": "living_room"}, "FALL")
time.sleep(5)
publish("home/fall-detection/events", {"event": "fall_escalated", "room": "living_room", "reason": "no_recovery"}, "ESCALATION")

# 3. Presence - same value 5 times but only the first should log
# Expected -> only 1 presence log for the 5 identical events and then one for the change
for i in range(5):
    publish("home/fall-detection/events", {"event": "presence_changed", "human": True, "room": "living_room"}, f"PRESENCE {i+1}")
publish("home/fall-detection/events", {"event": "presence_changed", "human": False, "room": "living_room"}, "PRESENCE CHANGE")

# 4. Radar failure
# Expected -> Telegram alert "Radar failure in living_room"
publish("home/fall-detection/events", {"event": "radar_failure", "room": "living_room"}, "RADAR FAILURE")

# 5. Heartbeat
# Expected -> no Telegram alert (just received by main.py)
publish("home/fall-detection/heartbeat", {"device_id": "xiao-fall-detector", "status": "alive"}, "HEARTBEAT")

# 6. Last Will (simulate ESP32 crash)
# Expected -> Telegram alert "Node disconnected from MQTT"
publish("home/fall-detection/status", {"status": "offline"}, "LAST WILL")

time.sleep(1)
client.loop_stop()
client.disconnect()
print("done")