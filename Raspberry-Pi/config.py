import os

# MQTT broker configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "home/fall-detection/#"

# Tiered alerting thresholds based on needle confidence
CONFIDENCE_HIGH   = 0.9 # >= 0.9: normal alert
CONFIDENCE_MEDIUM = 0.7 # >= 0.7: alert with warning
                        # < 0.7: alert and log for review

# Telegram bot configuration
TELEGRAM_BOT_TOKEN = "8254400683:AAEvVhYp4R7X9Rytm1x53MuOZA7L16XJlGo"

# Primary contact receives the first alert (child)
TELEGRAM_CHAT_PRIMARY = "8728165971"

# Secondary contact receives escaletion alert (family group chat)
TELEGRAM_CHAT_SECONDARY = "-5546381841"

# Escalation delay
ESCALATION_DELAY_SEC = 180 # 3 minutes

# Event log file - logs are stored with the scripts
LOG_FILE = os.path.join(os.path.dirname(__file__), "events.jsonl")