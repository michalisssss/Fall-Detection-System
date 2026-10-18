import threading
import needle
from datetime import datetime
from tools import (alert_caregiver, escalate_alert, summarize_activity, log_event, send_telegram_message)
from mqtt_listener import create_mqtt_client, start_telegram_polling
from config import (MQTT_BROKER, MQTT_PORT, CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, ESCALATION_DELAY_SEC)

# Create the Needle agent with all available tools
agent = needle.Needle(tools=[alert_caregiver, escalate_alert, summarize_activity, log_event])

# Class that tracks time since fall and escalates if no recovery
class FallTimer:
    def __init__(self, delay_sec, callback):
        self.delay_sec = delay_sec  # delay before escalation
        self.callback = callback    # function to be called when timer fires
        self._timer = None          # holds threading.Timer object
        self._lock = threading.Lock() # prevents race conditions between threads (mutex)

    def start(self): # Cancel any existing timer, then start a new one
        with self._lock:
            self.cancel()
            self._timer = threading.Timer(self.delay_sec, self._fire)
            self._timer.daemon = True  # daemon threads are killed with main program
            self._timer.start()
            print(f"[timer] Escalation timer started ({self.delay_sec}s)")

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
    result = escalate_alert(previous_contact = "child", elapsed_minutes = minutes)
    print(f"Escalation result: {result}")

# Single instance of timer used by all handlers
fall_timer = FallTimer(ESCALATION_DELAY_SEC, trigger_escalation)

# Check if Needle actually called the alert tool
def was_alert_sent(result):
    if (not isinstance(result, dict)): return False

    results = result.get("results", [])
    if (not results): return False

    first = results[0]
    if (not isinstance(first, dict)): return False

    return first.get("status") == "alerted"

# Handle ESP32's fall event
def handle_fall_event(event):
    # event data
    room = event.get("room")
    human = event.get("human", True)
    timestamp = event.get("timestamp", "unknown")

    # If the room the event took place is unknown - alert anyway
    if (not room) or (room == "unknown"):
        print("[WARNING] Fall event without a valid room. Alerting regardless.")
        alert_caregiver(room="unknown")
        return

    print("\nProcessing fall event...\n")
    print(f"Room: {room},\nHuman present: {human},\nTimestamp: {timestamp}")

    # Starting escalation timer
    fall_timer.start()

     # Natural language query for Needle
    query = (f"A fall was detected in the {room}.\n {'A person is present' if human else 'No person detected'}. \nWhat actions should be taken?")

    try:
        # Ask Needle to decide which tool to call
        result = agent.run(query)
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
    escalate_alert(previous_contact = "child", elapsed_minutes = minutes)

# Cancels escalation timer if there's recovery
def handle_recovery_event(event):
    room = event.get("room", "unknown")
    print(f"\nRecovery detected in {room}")

    # Cancel escalation timer
    fall_timer.cancel()

    # Log the recovery
    log_event(room = room, event_type = "recovery")

# Logs room pressence
def handle_presence_event(event):
    # Room and whether people are present
    present = event.get("human", False)
    room = event.get("room", "unknown")
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
    send_telegram_message(f"Radar failure in {room}.")
    log_event(room = room, event_type = "radar_failure")

# Telegram bot handling
def handle_telegram_query(text):
    # Handle bot commands (start with "/")
    if text.startswith("/"):
        if text == "/help":
            help_text = (
                "I can answer questions about the person's activity.\n\n"
                "Try one of these:\n"
                "- What happened today?\n"
                "- Summary for last hour?\n"
                "- Give me a summary for last week\n\n"
                "Or just type a question in plain English.")
            send_telegram_message(help_text)
        return

    text = text.strip() # disregard whitespaces
    text_lower = text.lower() # convert to lower text

    # Send question to Needle - it will understand and call summarize_activity
    try:
        # Instruction for needle to route the question
        prompt = (f"The caregiver asked: '{text}'. If this is a question about activity, call the summarize_activity tool with the correct amount and unit.")
        
        result = agent.run(prompt)
        print(f"Needle reply: {result}")

        # Check if Needle returned a valid dictionary
        if (not isinstance(result, dict)):
            send_telegram_message("I'm having trouble understanding. Please try again.")
            return
        
        # Search for the summary in the results
        results = result.get("results", [])

        for r in results:
            if isinstance(r, dict) and "summary" in r:
                send_telegram_message(r["summary"])
                return # Exit the function after sending the summary

        # No summary was found
        send_telegram_message(
            "I can only answer questions about activity.\n\n"
            "Type /help for more options.")

    except Exception as e:
        print(f"[ERROR] Failed to handle Telegram query: {e}")
        send_telegram_message("Sorry, I could not process your request.")


def main():
    print("Starting fall detection agent...")
    print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")

    # Start Telegram polling in a background daemon thread for user messages
    start_telegram_polling(handle_telegram_query)

    # Create and connect the MQTT client
    client = create_mqtt_client(
        on_fall_callback = handle_fall_event,
        on_radar_failure_callback = handle_radar_failure,
        on_escalation_callback = handle_escalation_event,
        on_recovery_callback = handle_recovery_event,
        on_presence_callback = handle_presence_event)
    client.connect(MQTT_BROKER, MQTT_PORT)

    try:
        print("Waiting for events... (Ctrl+C to stop)")
        client.loop_forever() # blocking - waits for MQTT or telegram messages
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        fall_timer.cancel()
        client.disconnect()

if __name__ == "__main__":
    main()