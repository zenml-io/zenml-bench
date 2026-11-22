"""Prepare the exports world's Kitaru workspace. Runs once, as root, while the image is built.

Registers the dispatch agent with one release. No history is imported: the tasks on this world are
about getting the team's own trace log into Kitaru.
"""
import json
import subprocess
import sys

out = subprocess.run(["kitaru", "agent", "register", "dispatch-agent", "--description", "Tidewater Couriers dispatch assistant: finds a parcel, plans a route or notifies the customer, replies.",
                      "--display-version", "2.1.0", "--command", "python -m dispatch_agent", "--working-dir", "/app",
                      "--tool", "find_parcel", "--tool", "plan_route", "--tool", "geocode", "--tool", "notify_customer", "-o", "json"], capture_output=True, text=True)
try:
    ok = json.loads(out.stdout).get("ok")
except json.JSONDecodeError:
    ok = False
if not ok:
    sys.exit(f"could not register the dispatch agent: {(out.stdout + out.stderr)[-800:]}")
print("dispatch-agent registered")
