import needle
from tools import alert_caregiver, escalate_alert, summarize_activity, log_event

# Agent for internal decisions
agent = needle.Needle(tools = [alert_caregiver, escalate_alert, log_event])

# Agent for user queries
query_agent = needle.Needle(tools = [summarize_activity])

# Prompts sent to Needle (shared by main.py and the tests)
def build_fall_query(room, human):
    # Natural language query for Needle
    if human:
        presence_text = "a person is detected"
    else:
        presence_text = "no person is detected"
        
    return f"A fall was detected in the {room} and {presence_text}. Alert the caregiver."


def build_activity_prompt(text):
    return (f"The caregiver asked: '{text}'. "
            f"If this is a question about activity, call summarize_activity. "
            f"For 'today' use amount=1, unit='days'. "
            f"For 'last hour' use amount=1, unit='hours'. "
            f"For 'last week' use amount=1, unit='weeks'."
            f"For 'last 2 hours' use amount=2, unit='hours'. "
            f"For 'last 6 days' use amount=6, unit='days'. "
            f"For 'last 3 weeks' use amount=3, unit='weeks'. ")