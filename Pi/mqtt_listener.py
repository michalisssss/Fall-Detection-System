import json
import threading
import time
import requests
import paho.mqtt.client as mqtt
from datetime import datetime
from config import (MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, TELEGRAM_BOT_TOKEN, MQTT_TOPIC_HEARTBEAT, MQTT_TOPIC_STATUS, HEARTBEAT_TIMEOUT_SEC)

# Create and configure the MQTT client
def create_mqtt_client(on_fall_callback, 
                       on_radar_failure_callback = None,
                       on_escalation_callback = None, 
                       on_recovery_callback = None,
                       on_presence_callback = None, 
                       on_heartbeat_callback = None,
                       on_status_callback = None):
    # Create the MQTT client with a unique ID
    client = mqtt.Client(callback_api_version = mqtt.CallbackAPIVersion.VERSION1, client_id = "pi-fall-detection")
    # Automatic reconnection with exponential backoff
    client.reconnect_delay_set(min_delay = 1, max_delay = 30)

    # Called automatically when the client connects to the broker
    def on_connect(client, userdata, flags, rc):
        if rc == 0:  # return code = 0 -> connection established
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

            print(f"Received on {msg.topic}: {payload}")
            event = payload.get("event")

            if msg.topic == MQTT_TOPIC_HEARTBEAT: # Heartbeat from ESP32
                if on_heartbeat_callback: on_heartbeat_callback(payload)
                return
            if msg.topic == MQTT_TOPIC_STATUS: # Last Will status (offline - ESP32 disconnected unexpectedly)
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
    # lists
    last_heartbeat = [time.time()]
    node_down = [False]   # True = node dead

    def on_heartbeat(payload):
        # heartbeat arrived - refresh time stamp
        last_heartbeat[0] = time.time()
        
        if node_down[0]: # heartbeat returned -> node is back
            node_down[0] = False
            if on_recovery_callback: on_recovery_callback()

    def monitor_loop():
        while True:
            time.sleep(10) # Check every 10 seconds
            # If node is not marked as down and there's no heartbeat within the timeout -> alert
            if (not node_down[0]) and (time.time() - last_heartbeat[0] > timeout_sec):
                node_down[0] = True # alert once per outage
                print(f"[heartbeat] No heartbeat for {timeout_sec}s")
                on_timeout_callback()

    # daemon thread
    threading.Thread(target = monitor_loop, daemon = True).start()
    print(f"[heartbeat] Monitor started (timeout={timeout_sec}s)")

     # Return the callback
    return on_heartbeat