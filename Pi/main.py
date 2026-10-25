import threading
from tools import (alert_caregiver, escalate_alert, summarize_activity, log_event, send_telegram_message)
from mqtt_listener import create_mqtt_client, start_telegram_polling, start_heartbeat_monitor
from config import (MQTT_BROKER, MQTT_PORT, ESCALATION_DELAY_SEC, TELEGRAM_CHAT_PRIMARY, TELEGRAM_CHAT_SECONDARY, PRIMARY_CONTACT_NAME, SECONDARY_CONTACT_NAME)
from agents import agent, query_agent, build_fall_query, build_activity_prompt

# Allowed chat IDs for user queries (caregivers)
ALLOWED_CHAT_IDS = {int(TELEGRAM_CHAT_PRIMARY), int(TELEGRAM_CHAT_SECONDARY)}

# Needle mutex
needle_lock = threading.Lock()

# Class that tracks time since fall and escalates if no recovery
class FallTimer:
    def __init__(self, delay_sec, callback):
        self.delay_sec = delay_sec  # delay before escalation
        self.callback = callback    # function to be called when timer fires
        self._timer = None          # holds threading.Timer object
        self._lock = threading.Lock() # prevents race conditions between threads (mutex)

    def start(self): # Cancel any existing timer and start a new one
        self._lock.acquire()   # mutex lock
        try:
            self.cancel()
            self._timer = threading.Timer(self.delay_sec, self._fire)
            self._timer.daemon = True  # daemon threads are killed with main program
            self._timer.start()
            print(f"[timer] Escalation timer started ({self.delay_sec}s)")
        finally:
            self._lock.release() # mutex unlock

    def cancel(self): # Stop the timer if it is running
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
            print("[timer] Escalation timer cancelled")

    def _fire(self): # escalation trigger
        print("[timer] Escalation delay elapsed")
        self.callback()

# Escalation 
def trigger_escalation():
    minutes = ESCALATION_DELAY_SEC // 60 # // -> result is in int
    result = escalate_alert(previous_contact = PRIMARY_CONTACT_NAME, elapsed_minutes = minutes)
    print(f"Escalation result: {result}")

# Single instance of timer used by all handlers
fall_timer = FallTimer(ESCALATION_DELAY_SEC, trigger_escalation)

# Check if Needle called the alert tool
def was_alert_sent(result):
    # Check if the result is a dictionary
    if not isinstance(result, dict): return False

    # Get list of results from Needle
    results = result.get("results", [])
    if not results: return False

    if not isinstance(results, list): return False

    # Check if the first result is a dictionary
    if not isinstance(results[0], dict): return False

    # Check if the status is "alerted"
    status = results[0].get("status")
    if status == "alerted":
        return True
    else:
        return False

# Handle ESP32's fall event
def handle_fall_event(event):
    # event data
    room = event.get("room")
    human = event.get("human", True)
    timestamp = event.get("timestamp", "unknown")

    # Starting escalation timer
    fall_timer.start()
    
    # If the room the event took place is unknown - alert anyway
    if (not room) or (room == "unknown"):
        print("[WARNING] Fall event without a valid room. Alerting regardless.")
        alert_caregiver(room="unknown")
        return

    print("\nProcessing fall event...\n")
    print(f"Room: {room},\nHuman present: {human},\nTimestamp: {timestamp}")

    # Natural language query for Needle
    query = build_fall_query(room, human)

    try:
        # Wait 5 seconds - needle may be in use right now
        if not needle_lock.acquire(timeout = 5):
            print("[WARNING] Needle busy. Sending fallback alert.")
            alert_caregiver(room = room)
            return
        try:
            result = agent.run(query)
        finally:
            needle_lock.release()
        print(f"Needle decision: {result}")

        # if Needle did not alert - send a fallback alert
        if (not was_alert_sent(result)):
            print("[WARNING] Needle did not alert. Sending fallback alert.")
            alert_caregiver(room = room)
    # If Needle crashes - still send an alert
    except Exception as e:
        print(f"[ERROR] Needle failed to process event: {e}")
        alert_caregiver(room = room)

# Handles escalation reported by the ESP32
def handle_escalation_event(event):
    # Room of event and reason of escalation
    room = event.get("room", "unknown")
    reason = event.get("reason", "unknown")
    print(f"[ESCALATION] Room={room}, reason={reason}")

    # Cancel the Pi-side escalation timer - the ESP32 already escalated
    fall_timer.cancel()

    minutes = ESCALATION_DELAY_SEC // 60
    escalate_alert(previous_contact = PRIMARY_CONTACT_NAME, elapsed_minutes = minutes)

# Cancels escalation timer if there's recovery
def handle_recovery_event(event):
    room = event.get("room", "unknown")
    print(f"\nRecovery detected in {room}")

    # Cancel escalation timer
    fall_timer.cancel()

    # Inform of recovery
    send_telegram_message(f"The person in the {room} appears to have recovered.")

    # Log the recovery
    log_event(room = room, event_type = "recovery")

# Last known presence per room
last_presence = {}

# Logs room pressence
def handle_presence_event(event):
    # Room and whether people are present
    present = event.get("human", False)
    room = event.get("room", "unknown")

    # Ignore events that don't change anything
    if last_presence.get(room) == present:
        return
    last_presence[room] = present

    if present: 
        status = "present" 
    else: 
        status = "absent"
    print(f"[PRESENCE] {room}: {status}")

    # Log room pressence
    log_event(room = room, event_type = "presence")

# Logs radar failure
def handle_radar_failure(event):
    # Room where radar failed
    room = event.get("room", "unknown")
    print(f"[WARNING] Radar failure in {room}")

    # Alert caregiver of radar failure
    send_telegram_message(f"Radar failure in {room}. The system may not detect falls.")
    log_event(room = room, event_type = "radar_failure")

# Telegram bot handling
def handle_telegram_query(text, chat_id = None):
    # Ignore messages from unknown chats
    if chat_id is None or int(chat_id) not in ALLOWED_CHAT_IDS:
        print(f"[telegram] Ignored message from unauthorized chat {chat_id}")
        return
    
    # Handle bot commands (start with "/")
    if text.startswith("/"):
        if text == "/help":
            help_text = (
                "I can answer questions about the person's activity.\n\n"
                "Try one of these:\n"
                "- What happened today?\n"
                "- Summary for last hour?\n"
                "- Give me a summary for last week\n\n"
                "Or just type a question in English.")
            send_telegram_message(help_text, chat_id = chat_id)
        return

    text = text.strip() # disregard whitespaces

    # Send question to needle - it will understand and call summarize_activity
    try:
        # Instruction for needle to route the question
        prompt = build_activity_prompt(text)
        
        needle_lock.acquire()
        try:
            result = query_agent.run(prompt)
        finally:
            needle_lock.release()
        print(f"Needle reply: {result}")

        # Check if Needle returned a valid dictionary
        if (not isinstance(result, dict)):
            send_telegram_message("I'm having trouble understanding. Please try again.", chat_id = chat_id)
            return
        
        # Search for the summary in the results
        results = result.get("results", [])

        # needle calls summary tool
        for r in results:
            if isinstance(r, dict) and "summary" in r:
                send_telegram_message(r["summary"], chat_id = chat_id)
                return # Exit the function after sending the summary

        # Fallback in case needle supressed summary tool
        if isinstance(result, dict) and result.get("suppressed_calls"):
            for call in result["suppressed_calls"]:
                if call["name"] == "summarize_activity":
                    args = call["arguments"]
                    summary = summarize_activity(args["amount"], args["unit"])
                    send_telegram_message(summary["summary"], chat_id=chat_id)
                    return
        
        # No summary was found
        send_telegram_message(
            "I can only answer questions about activity.\n\n"
            "Type /help for more options.", chat_id = chat_id)

    except Exception as e:
        print(f"[ERROR] Failed to handle Telegram query: {e}")
        send_telegram_message("Sorry, I could not process your request.", chat_id = chat_id)


def main():
    print(f"Starting fall detection agent... Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")

    # Heartbeat monitor
    def on_heartbeat_timeout():
        send_telegram_message("Warning: the fall detection node is not responding. Falls may not be detected.")

    def on_node_recovered():
        send_telegram_message("The fall detection node is back online.")

    def on_status(payload):   # Last Will message from the broker
        if payload.get("status") == "offline":
            send_telegram_message("Warning: the fall detection node disconnected unexpectedly.")
    
    # Start Telegram polling in a background daemon thread for user messages
    start_telegram_polling(handle_telegram_query)

    # Start heartbeat monitor and get the callback to register
    on_heartbeat_callback = start_heartbeat_monitor(on_heartbeat_timeout, on_node_recovered)

    # Create and connect the MQTT client
    client = create_mqtt_client(
        on_fall_callback = handle_fall_event,
        on_radar_failure_callback = handle_radar_failure,
        on_escalation_callback = handle_escalation_event,
        on_recovery_callback = handle_recovery_event,
        on_presence_callback = handle_presence_event,
        on_heartbeat_callback = on_heartbeat_callback,
        on_status_callback = on_status) 
    
    client.connect_async(MQTT_BROKER, MQTT_PORT)   # does not fail if the broker is down
    print("Attempting to connect to MQTT (will retry if broker is down)...")
    try:
        print("Waiting for events... (Ctrl+C to stop)")

        # blocking - waits for MQTT or telegram messages
        client.loop_forever(retry_first_connection = True) # True -> keeps trying to connect until the broker is available
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        fall_timer.cancel()
        client.disconnect()

if __name__ == "__main__":
    main()