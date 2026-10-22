import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import handle_telegram_query, ALLOWED_CHAT_IDS
from config import TELEGRAM_CHAT_PRIMARY

print(f"allowed chat ids: {ALLOWED_CHAT_IDS}")

print("\n[unknown chat] should be ignored")
handle_telegram_query("What happened today?", chat_id = 999999999)

print("\n[None chat] should be ignored")
handle_telegram_query("What happened today?", chat_id = None)

print("\n[known chat] should query Needle and send summary")
handle_telegram_query("What happened today?", chat_id = int(TELEGRAM_CHAT_PRIMARY))

print("\ndone")