import needle
from tools import alert_caregiver, escalate_alert, summarize_activity, log_event

# Agent for internal decisions
agent = needle.Needle(tools = [alert_caregiver, escalate_alert, log_event])

# Agent for user queries
query_agent = needle.Needle(tools = [summarize_activity])