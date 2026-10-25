import sys
import os
# Add parent directory (Pi/) to sys.path so main.py can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import handle_telegram_query, ALLOWED_CHAT_IDS
from config import TELEGRAM_CHAT_PRIMARY, TELEGRAM_CHAT_SECONDARY

print(f"allowed chat ids: {ALLOWED_CHAT_IDS}")

# Unknown chat -> should be silently ignored
print("\n[unknown chat] should be ignored")
handle_telegram_query("What happened today?", chat_id = 999999999)

# Unknown chat with a command -> should still be ignored
print("\n[unknown chat /help] should be ignored")
handle_telegram_query("/help", chat_id = 999999999)

# None chat_id -> should be silently ignored
print("\n[None chat] should be ignored")
handle_telegram_query("What happened today?", chat_id = None)

# Known primary chat -> should query Needle and send a summary
print("\n[known chat] should query Needle and send summary")
handle_telegram_query("What happened today?", chat_id = int(TELEGRAM_CHAT_PRIMARY))

# Known secondary chat -> should also be allowed
print("\n[secondary chat] should also be allowed")
handle_telegram_query("What happened today?", chat_id = int(TELEGRAM_CHAT_SECONDARY))

# Known chat with a command -> should send the help text
print("\n[known chat /help] should send help text")
handle_telegram_query("/help", chat_id = int(TELEGRAM_CHAT_PRIMARY))

print("\ndone")