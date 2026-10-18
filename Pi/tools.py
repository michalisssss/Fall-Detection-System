import json
import os
import needle
import requests
from datetime import datetime, timedelta
from config import (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_PRIMARY, TELEGRAM_CHAT_SECONDARY, LOG_FILE)

# Send fall alert to caregiver
def send_telegram_message(message: str, chat_id: str = None) -> bool:
    # Default chat ID is the primary caregiver
    if chat_id is None: chat_id = TELEGRAM_CHAT_PRIMARY

    # Telegram Bot API endpoint and payload
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

    try:
        # Send the HTTP POST request with 10s timeout
        response = requests.post(url, data = payload, timeout = 10)

        # Telegram accepted the message
        if response.status_code == 200:
            print(f"[telegram] Sent to {chat_id}")
            return True

        # Any other status code means the send failed
        print(f"[telegram] Failed for {chat_id}: {response.status_code}")
        return False

    except Exception as e:
        print(f"[telegram] Error for {chat_id}: {e}")
        return False
    
# Append record of events to the JSONL log file
def append_log(record: dict):
    try:
        f = open(LOG_FILE, "a", encoding="utf-8")
        f.write(json.dumps(record) + "\n")  # JSONL = each record is a JSON object on its own line
    except Exception as e:
        print(f"[log] Failed to write to {LOG_FILE}: {e}")
    finally:
        if f is not None: 
            f.close()

# Read all log records with a timestamp >= the given cutoff and return them
def read_log_since(since: datetime) -> list:
    records = []
    try:
        # Open the log file for reading
        f = open(LOG_FILE, "r", encoding="utf-8")
        # Process the file line by line (one JSON object per line)
        for line in f:
            line = line.strip() # disregard whitespaces

            # Skip empty lines
            if not line: continue

            try:
                # Parse JSON object
                record = json.loads(line)

                # Convert timestamp string to a datetime object
                ts = datetime.strptime(record.get("time", ""), "%Y-%m-%d %H:%M:%S")

                # Keep only records newer than the cutoff
                if ts >= since: records.append(record)

            # Skip malformed lines
            except Exception: 
                continue

    # The log file doesn't exist yet - return empty list
    except FileNotFoundError:   
        print(f"[log] No log file found at {LOG_FILE}")
    finally:
        if f is not None:
            f.close()

    return records

@needle.tool
def alert_caregiver(room: str):
    """Send an alert to the primary caregiver for a detected fall.

    Use this ONLY when a fall has been detected and confirmed.
    Do NOT use this for questions about presence, activity, or rooms.
    Do NOT use this for general inquiries.

    Args:
        room: The room where the fall occurred (e.g., "living_room").
    """
    # Severity is high for a detected fall
    severity = "high"

    # Current time
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Αlert message
    message = (f"FALL DETECTED \nRoom: {room} \nSeverity: {severity} \nTime: {timestamp}")

    # Send alert to the primary caregiver
    send_telegram_message(message)

    # Record the event in the log
    append_log({"event": "fall", "room": room, "severity": severity, "time": timestamp})

    print(f"[{timestamp}] [ALERT] Fall in {room}, severity={severity}")

    return {"status": "alerted", "room": room, "severity": severity}


@needle.tool
def escalate_alert(previous_contact: str, elapsed_minutes: int):
    """Escalate to a secondary contact ONLY if the primary caregiver did not respond.

    Use this after a delay, and only after alert_caregiver has already been called.
    Do NOT use this for the initial alert.

    Args:
        previous_contact: The person who was notified but did not respond.
        Must be one of: "child", "family".

        elapsed_minutes: Minutes passed since the first alert without a response.
    """
    # Current time
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Escalation message
    message = (f"ESCALATION \n{previous_contact} did not respond in {elapsed_minutes} minutes.\nTime: {timestamp}")

    # Escalation always goes to the secondary contact (family group)
    send_telegram_message(message, chat_id = TELEGRAM_CHAT_SECONDARY)

    # Record escalation
    append_log({"event": "escalation", "contact": previous_contact, "time": timestamp})

    print(f"[{timestamp}] [ESCALATE] {previous_contact} did not respond in {elapsed_minutes} minutes")

    return {"status": "escalated", "previous_contact": previous_contact}


@needle.tool
def summarize_activity(amount: int, unit: str):
    """Generate a summary of activity for a specific time period.

    Use this when the caregiver asks what happened recently.
    Do NOT use this for real-time alerts or fall notifications (use alert_caregiver for those).

    Args:
        amount: The number of time units to look back (e.g., 1, 3, 7).
        unit: The time unit. Must be one of: "hours", "days", "weeks".
    """
    # Calculate the cutoff time dynamically based on the input
    now = datetime.now()
    if unit == "hours":
        since = now - timedelta(hours = amount)
    elif unit == "days":
        since = now - timedelta(days = amount)
    elif unit == "weeks":
        since = now - timedelta(weeks = amount)
    else: # Fallback
        since = now - timedelta(hours = 1) 

    # Load all log records after that cutoff
    records = read_log_since(since)

    # Count events by type
    fall_count = 0
    presence_count = 0
    radar_failure_count = 0

    for record in records:
        event = record.get("event")
        if event == "fall":
            fall_count += 1
        elif event == "presence":
            presence_count += 1
        elif event == "radar_failure":
            radar_failure_count += 1

   # Human-readable summary
    time_label = f"last {amount} {unit}"
    summary = (f"Activity summary for {time_label}: \n{fall_count} falls, \n{presence_count} presence changes, \n{radar_failure_count} radar failures.")

    print(f"[summary] {summary}")
    return {"summary": summary}


@needle.tool
def log_event(room: str, event_type: str):
    """Log a non-critical event for later review by a caregiver.

    Use this to record presence changes, system status, or diagnostic events.
    Do NOT use this for fall alerts or escalations.

    Args:
        room: The room where the event occurred (e.g., "living_room").

        event_type: Type of event.
            Must be one of: "presence", "radar_failure", "system_boot", "recovery".
    """
    # Get the current time
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Append the event to the log file
    append_log({"event": event_type, "room": room, "time": timestamp})

    print(f"[{timestamp}] [LOG] {event_type} in {room}")

    return {"status": "logged", "room": room, "event_type": event_type}