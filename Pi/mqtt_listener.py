import json
import threading
import time
import requests
import paho.mqtt.client as mqtt
from datetime import datetime
from config import (MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, TELEGRAM_BOT_TOKEN)

# Create and configure the MQTT client
def create_mqtt_client(on_fall_callback, on_radar_failure_callback = None, on_escalation_callback = None, on_recovery_callback = None, on_presence_callback = None):
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
            print(f"Subscribed to {MQTT_TOPIC}")
        else:
            print(f"MQTT connection failed, rc={rc}")

    # Called automatically when a message arrives on a subscribed topic
    def on_message(client, userdata, msg):
        try:
            # Decode the payload into a Python dictionary
            payload = json.loads(msg.payload.decode())

            # JSON object (dictionary) is expected
            if (not isinstance(payload, dict)):
                print(f"Unexpected JSON type: {type(payload)}")
                return

            # Override the timestamp with the Pi's local time
            payload["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"Received on {msg.topic}: {payload}")
            event = payload.get("event")

            # Fall detected and confirmed
            if event == "fall" and payload.get("fall"): on_fall_callback(payload)

            # Fall escalation (ESP32-side escalation)
            elif event == "fall_escalated":
                if on_escalation_callback: on_escalation_callback(payload)
                else: print("[WARNING] Fall escalation received (no handler)")

            # Fall recovery (the person has stood up)
            elif event == "state_change" and (not payload.get("fall")):
                if on_recovery_callback: on_recovery_callback(payload)
                else: print("[INFO] Recovery received (no handler)")

            # Presence change (person entered or left the room)
            elif event == "presence_changed":
                if on_presence_callback: on_presence_callback(payload)
                else: print("[INFO] Presence change received (no handler)")

            # Radar failure
            elif event == "radar_failure":
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


# Start a background thread that polls Telegram for new messages
def start_telegram_polling(on_query_callback):
    def poll_loop():
        offset = None # offset is used to acknowledge processed updates
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

        # Run forever (daemon thread - it stops with the program)
        while True:
            try:
                # Long polling: wait up to 30s for new messages
                params = {"timeout": 30}
                if offset is not None: params["offset"] = offset
                response = requests.get(url, params = params, timeout = 35)

                # If Telegram returned an error, wait a bit and retry
                if response.status_code != 200:
                    time.sleep(5)
                    continue

                data = response.json()

                # Process each incoming update
                for update in data.get("result", []):
                    # Advance the offset so this update is not processed again
                    offset = update["update_id"] + 1

                    message = update.get("message", {})
                    text = message.get("text")

                    # Only handle text messages
                    if text:
                        print(f"[telegram] Incoming: {text}")
                        on_query_callback(text)

            except Exception as e:
                print(f"[telegram] Polling error: {e}")
                time.sleep(5)

    # Start the polling thread as a daemon
    thread = threading.Thread(target = poll_loop, daemon = True)
    thread.start()
    print("[telegram] Polling started")