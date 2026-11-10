import json
import threading
import time
import requests
import paho.mqtt.client as mqtt
from datetime import datetime
from config import (MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, TELEGRAM_BOT_TOKEN, HEARTBEAT_TIMEOUT_SEC, EXPECTED_ROOMS)


# Create and configure the MQTT client
def create_mqtt_client(on_fall_callback, on_radar_failure_callback = None, on_escalation_callback = None, on_recovery_callback = None,on_presence_callback = None, on_heartbeat_callback = None, on_status_callback = None):
    # Create the MQTT client with a unique ID
    client = mqtt.Client(callback_api_version = mqtt.CallbackAPIVersion.VERSION2, client_id = "pi-fall-detection")
    # Automatic reconnection with exponential backoff
    client.reconnect_delay_set(min_delay = 1, max_delay = 30)

    # Called automatically when the client connects to the broker
    def on_connect(client, userdata, flags, rc, properties):
        if rc == 0:  # return code == 0 -> connection established
            print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            # Subscribe to all topics under home/fall-detection/
            client.subscribe(MQTT_TOPIC)
            print(f"Subscribed to {MQTT_TOPIC} (events, heartbeat, status)")
        else:
            print(f"MQTT connection failed, rc={rc}")

    # Called automatically when a message arrives from ESP32
    def on_message(client, userdata, msg):
        try:
            # Decode the payload into a Python dictionary
            payload = json.loads(msg.payload.decode())

            # Check if the JSON type is dictionary
            if not isinstance(payload, dict):
                print(f"Unexpected JSON type: {type(payload)}")
                return

            # Override the timestamp with the Pi's local time
            payload["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Extract room from topic: home/fall-detection/{room}/{topic_type}
            topic_parts = msg.topic.split('/')
            room = topic_parts[2] if len(topic_parts) >= 3 else "unknown"
            topic_type = topic_parts[3] if len(topic_parts) >= 4 else "unknown"
            
            # Add room to payload if not already present
            if "room" not in payload:
                payload["room"] = room

            print(f"Received on {msg.topic}: {payload}")
            event = payload.get("event")

            if topic_type == "heartbeat": # Heartbeat from ESP32
                if on_heartbeat_callback: on_heartbeat_callback(payload)
                return
            if topic_type == "status": # Last Will status (offline - ESP32 disconnected unexpectedly)
                if on_status_callback: on_status_callback(payload)
                return

            if event == "fall" and payload.get("fall"): # Fall detected and confirmed
                on_fall_callback(payload)
            elif event == "fall_escalated": # Fall escalation (ESP32-side escalation)
                if on_escalation_callback: on_escalation_callback(payload)
                else: print("[WARNING] Fall escalation received (no handler)")
            elif event == "state_change" and (not payload.get("fall")): # Fall recovery (the person has stood up)
                if on_recovery_callback: on_recovery_callback(payload)
                else: print("[INFO] Recovery received (no handler)")
            elif event == "presence_changed": # Presence change (person entered or left the room)
                if on_presence_callback: on_presence_callback(payload)
                else: print("[INFO] Presence change received (no handler)") 
            elif event == "radar_failure": # Radar failure
                if on_radar_failure_callback: on_radar_failure_callback(payload)
                else: print("[WARNING] Radar failure detected")

        except json.JSONDecodeError: # The payload was not valid JSON
            print(f"Invalid JSON received: {msg.payload}")
        except Exception as e:
            print(f"Error handling message: {e}")

    # Register the callbacks and return the client
    client.on_connect = on_connect
    client.on_message = on_message
    return client


# Start a background thread that polls Telegram for new messages from caregiver
def start_telegram_polling(on_query_callback):
    # loops forever asking telegram for new messages
    def poll_loop():
        # offset tracks the next message ID to avoid fetching the same messages twice
        offset = None 
        # endpoint of messages
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

        # Run forever (daemon thread - it stops with the program)
        while True:
            try:
                # New dictionary for each request
                params = {} 

                # Long polling - wait up to 30s for new messages
                params["timeout"] = 30

                # If there is an offset - let telegram send only new messages
                if offset is not None: params["offset"] = offset
                response = requests.get(url, params = params, timeout = 35)

                # If there's an error - retry after 5 seconds
                if response.status_code != 200:
                    time.sleep(5)
                    continue

                # Convert JSON response to dictionary
                data = response.json()

                # Process each incoming update
                for update in data.get("result", []):
                    # Advance the offset so this update is not processed again
                    offset = update["update_id"] + 1

                    # extract message data
                    message = update.get("message", {})
                    text = message.get("text")
                    chat_id = message.get("chat", {}).get("id")   # who sent it

                    # Only handle text messages
                    if text:
                        print(f"[telegram] Incoming: {text}")
                         # Pass text to the main program (handle_telegram_query)
                        on_query_callback(text, chat_id)

            except Exception as e:
                print(f"[telegram] Polling error: {e}")
                time.sleep(5)

    # Start the polling thread as a daemon
    thread = threading.Thread(target = poll_loop, daemon = True)
    thread.start()
    print("[telegram] Polling started")

def start_heartbeat_monitor(on_timeout_callback, on_recovery_callback = None, timeout_sec = HEARTBEAT_TIMEOUT_SEC):
    # Dictionary to track the last heartbeat time per room ("living_room": timestamp, "bathroom": timestamp, ...)
    last_heartbeat = {}   
    # Dictionary to track which rooms are currently down ("living_room": False, "bathroom": True, ...)
    node_down = {} 

    # Initialize all expected rooms with current time (so they don't trigger immediately)
    for room in EXPECTED_ROOMS:
        last_heartbeat[room] = time.time()
        node_down[room] = False

    def on_heartbeat(payload):
        # Extract the room from the payload
        room = payload.get("room", "unknown")

        # Refresh the timestamp for this specific room
        last_heartbeat[room] = time.time()
    
        # If this room was marked as down, it is now back online
        if node_down.get(room, False):
            node_down[room] = False
            print(f"[heartbeat] {room} is back online")
            if on_recovery_callback:
                on_recovery_callback(room)  # Pass the room to the callback

    def monitor_loop():
        while True:
            time.sleep(10)  # Check every 10 seconds
            now = time.time()
            
            # Iterate over all rooms that have sent at least one heartbeat
            for room, last_time in last_heartbeat.items():
                # If the room is not marked as down and the timeout has passed
                if not node_down.get(room, False) and (now - last_time > timeout_sec):
                    node_down[room] = True  # Mark as down (alert once per outage)
                    print(f"[heartbeat] No heartbeat from {room} for {timeout_sec}s")
                    on_timeout_callback(room)  # Pass the room to the callback

    # Monitor runs in a daemon thread so it stops with the main program
    threading.Thread(target = monitor_loop, daemon = True).start()
    print(f"[heartbeat] Monitor started (timeout={timeout_sec}s)")

    # Return the callback so it can be registered with the MQTT client
    return on_heartbeat