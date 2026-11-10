import time
import json
import paho.mqtt.client as mqtt

# Connect to the MQTT broker
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="test-heartbeat")
client.connect("localhost", 1883)
client.loop_start()

def publish_heartbeat(room):
    payload = json.dumps({"device_id": f"xiao-{room}", "status": "alive", "room": room})
    topic = f"home/fall-detection/{room}/heartbeat"
    result = client.publish(topic, payload)
    if result.rc == 0:
        print(f"[HEARTBEAT] {room}: {payload}")
    else:
        print(f"[ERROR] {room}: publish failed (rc={result.rc})")

print("Heartbeat multi-room test")
print("Sending heartbeats from bathroom and kitchen...\n")

# Send one heartbeat from both rooms
publish_heartbeat("bathroom")
publish_heartbeat("kitchen")

print("\nNow stopping heartbeats from bathroom (simulating node down)...")
print("Kitchen will keep sending heartbeats every 10 seconds.\n")

# Keep sending heartbeats from kitchen for 130 seconds (timeout is 120s)
for i in range(13):
    time.sleep(10)
    publish_heartbeat("kitchen")
    print(f"[{i+1}/13] Kitchen heartbeat sent. Bathroom is silent for {(i+1)*10}s...")

print("\nDone")

time.sleep(1)
client.loop_stop()
client.disconnect()