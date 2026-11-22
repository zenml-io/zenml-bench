#!/usr/bin/env bash
# Builds the state the task starts from: five nights imported correctly, some tickets reviewed into a cohort, then the
# script changed and two more nights imported with it. Runs as root while the image is built.
set -euo pipefail
kitaru agent register support-assistant --description "Tidewater Couriers support assistant" --display-version 1.5.0 --command "python -m support_assistant" --working-dir /app \
  --tool lookup_shipment --tool open_claim --tool schedule_redelivery --tool send_email -o json > /dev/null
for night in 01 02 03 04 05; do bash /opt/setup/nightly_import.v1.sh /app/exports/nightly/support-2026-08-$night.jsonl > /dev/null; done
python3 - <<'PY'
import json, subprocess
def kitaru(*args):
    out = json.loads(subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True).stdout)
    assert out["ok"], out
    return out
sessions = kitaru("session", "list", "--agent", "support-assistant", "--size", "1000")["items"]
assert len(sessions) == 120, len(sessions)
reviewed = sorted(sessions, key=lambda s: s["external_id"])[50:120:3]   # tickets of days three to five, every third one
open("/tmp/reviewed.txt", "w").write("\n".join(s["id"] for s in reviewed) + "\n")
cohort = kitaru("cohort", "create", "reviewed-week-31", "--agent", "support-assistant", "--description", "Tickets the support leads read in week 31.", "--sessions-file", "/tmp/reviewed.txt")
agent = kitaru("agent", "get", "support-assistant")["item"]
json.dump({"agent_id": agent["id"], "cohort_id": kitaru("cohort", "get", "reviewed-week-31")["item"]["id"], "cohort_members": sorted(s["id"] for s in reviewed),
           "originals": {s["external_id"]: s["id"] for s in sessions}}, open("/etc/kitaru-bench/i4.json", "w"))
PY
chmod 600 /etc/kitaru-bench/i4.json   # the grader's record of what was there before the agent started; root only
for night in 06 07; do bash /opt/setup/nightly_import.v2.sh /app/exports/nightly/support-2026-08-$night.jsonl > /dev/null; done
test "$(kitaru session list --agent support-assistant --size 1000 -o json | python3 -c 'import sys, json; print(len(json.load(sys.stdin)["items"]))')" = 216
# The repository's history shows when the script changed.
cp /opt/setup/nightly_import.v1.sh /tmp/v1.sh; cp /opt/setup/nightly_import.v2.sh /tmp/v2.sh; chmod a+r /tmp/v1.sh /tmp/v2.sh
runuser -u agent -- bash -c 'cd /app && export GIT_AUTHOR_NAME=tidewater GIT_AUTHOR_EMAIL=dev@tidewater.example GIT_COMMITTER_NAME=tidewater GIT_COMMITTER_EMAIL=dev@tidewater.example \
  && cp /tmp/v1.sh bin/nightly_import.sh && chmod +x bin/nightly_import.sh && git add -A \
  && GIT_AUTHOR_DATE=2026-07-28T09:00:00Z GIT_COMMITTER_DATE=2026-07-28T09:00:00Z git commit -q --amend -m "Support assistant workspace" \
  && cp /tmp/v2.sh bin/nightly_import.sh && git add -A \
  && GIT_AUTHOR_DATE=2026-08-05T16:40:00Z GIT_COMMITTER_DATE=2026-08-05T16:40:00Z git commit -q -m "nightly import: name the source after the file, so staging exports can use the same script"'
echo "i4 state ready"
