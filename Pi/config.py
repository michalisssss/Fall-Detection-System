import os

# MQTT broker configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "home/fall-detection/#"

HEARTBEAT_TIMEOUT_SEC = 120  # 2 minutes without heartbeat = node down
MQTT_TOPIC_HEARTBEAT = "home/fall-detection/heartbeat"
MQTT_TOPIC_STATUS = "home/fall-detection/status"

# Telegram bot configuration
TELEGRAM_BOT_TOKEN = "" ###########################################################

# Primary contact receives the first alert 
TELEGRAM_CHAT_PRIMARY = ""

# Secondary contact (group chat) receives escaletion alert
TELEGRAM_CHAT_SECONDARY = ""

# Escalation delay (15 seconds more than the ESP32 escalation timeout so there is no double escaltion)
ESCALATION_DELAY_SEC = 195 # 3 minutes and 15 seconds

# Event log file - logs are stored with the scripts
LOG_FILE = os.path.join(os.path.dirname(__file__), "events.jsonl")