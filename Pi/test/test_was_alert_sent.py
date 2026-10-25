import sys
import os
# Add parent directory (Pi/) to sys.path so main.py can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import was_alert_sent


# (input, expected result) pairs for each test case
tests = [
    ({"results": [{"status": "alerted"}]}, True),       # alert was sent
    ({"results": {"status": "alerted"}}, False),        # results is a dict - not a list
    ({"results": [{"status": "logged"}]}, False),       # wrong status
    ({"results": []}, False),                           # empty results
    ({"results": None}, False),                         # results is None
    (None, False),                                      # input is None
    ("not a dict", False),                              # input is not a dict
    ({"results": [{"summary": "test"}]}, False),        # summary - not alert
    ({"results": [None]}, False),                       # first result is None
    ({"results": "not a list"}, False),                 # results is a string
    ({}, False),                                        # no "results" key 
]

print("Testing was_alert_sent()...\n")

passed = 0

# Run all tests
for i in range(len(tests)):
    (input, expected) = tests[i]
    try:
        result = was_alert_sent(input)
    except Exception as e: # Catch exceptions so the test loop keeps running
        result = f"EXCEPTION: {e}"

    if result == expected:
        passed += 1
        print(f"[PASS] test {i}: {result} (expected {expected})")
    else:
        print(f"[FAIL] test {i}: {result} (expected {expected})")

print(f"\n{passed}/{len(tests)} passed")