import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import was_alert_sent


# Test cases
tests = [
    # (input, expected)
    ({"results": [{"status": "alerted"}]}, True),
    ({"results": [{"status": "logged"}]}, False),
    ({"results": []}, False),
    ({"results": None}, False),
    (None, False),
    ("not a dict", False),
    ({"results": [{"summary": "test"}]}, False),
    ({"results": [None]}, False),
    ({"results": "not a list"}, False), 
    ({}, False),                          
]

print("Testing was_alert_sent()...\n")

passed = 0

for i, (input_val, expected) in enumerate(tests, 1):
    try:
        result = was_alert_sent(input_val)
    except Exception as e:
        result = f"EXCEPTION: {e}"

    ok = result == expected
    if ok:
        passed += 1
    print(f"[{'PASS' if ok else 'FAIL'}] test {i}: {result} (expected {expected})")

print(f"\n{passed}/{len(tests)} passed")