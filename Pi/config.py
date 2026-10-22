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

# Primary contact receives the first alert (child)
TELEGRAM_CHAT_PRIMARY = "8728165971"

# Secondary contact receives escaletion alert (family group chat)
TELEGRAM_CHAT_SECONDARY = "-5546381841"

# Escalation delay
ESCALATION_DELAY_SEC = 180 # 3 minutes

# Event log file - logs are stored with the scripts
LOG_FILE = os.path.join(os.path.dirname(__file__), "events.jsonl")