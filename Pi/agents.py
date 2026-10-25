import needle
from tools import alert_caregiver, escalate_alert, summarize_activity, log_event

# Agent for internal decisions
agent = needle.Needle(tools = [alert_caregiver, escalate_alert, log_event], stateless = True)

# Agent for user queries
query_agent = needle.Needle(tools = [summarize_activity], stateless = True)

# Prompt builder for fall events (shared by main.py and the tests)
def build_fall_query(room, human):
    # Natural language query for Needle
    if human:
        presence_text = "a person is detected"
    else:
        presence_text = "no person is detected"
        
    return (f"A fall was detected in the {room} and {presence_text}. "
            f"Call alert_caregiver with room='{room}'. "
            f"Do NOT call escalate_alert.")

# Prompt builder for activity queries (shared by main.py and the tests)
def build_activity_prompt(text):
    return (f"The caregiver asked: '{text}'. "
            f"This is a question about activity. You MUST call summarize_activity. "
            f"If no time period is mentioned, use amount=1, unit='days'. "
            f"Extract the number N and the unit from the request. "
            f"For 'last N hours' use amount=N, unit='hours'. "
            f"For 'last N days' use amount=N, unit='days'. "
            f"For 'last N weeks' use amount=N, unit='weeks'. "
            f"For 'last N months' use amount=N, unit='months'. "
            f"For 'today' use amount=1, unit='days'. "
            f"For 'yesterday' use amount=1, unit='days'. ")