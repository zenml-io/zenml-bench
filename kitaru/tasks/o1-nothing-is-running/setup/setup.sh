#!/usr/bin/env bash
# Builds the state the task starts from: no worker, the team's start script, and work that is waiting. Runs as root while the image is built.
set -euo pipefail
/opt/kitaru-bench/stop.sh --workers
sleep 3
python3 - <<'PY'
import json, os, subprocess, tempfile
from pathlib import Path
def cli(*args):
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    data = json.loads(out.stdout or out.stderr)
    assert data.get("ok"), (args, json.dumps(data)[:400])
    return data
before = json.load(open("/etc/kitaru-bench/helpdesk.json"))
version = before["versions"]["2.0.0"]
script = Path("/app/bin/start_worker.sh")
script.parent.mkdir(exist_ok=True)
script.write_text(f"""#!/usr/bin/env bash
# Starts this machine's Kitaru worker. It stays in the foreground until it is stopped.
set -euo pipefail
cd "$(dirname "$0")/.."
exec kitaru worker start --name helpdesk-worker --concurrency 4 \\
  --claim agent={version} \\
  --claim importer
""")
script.chmod(0o755)
subprocess.run(["chown", "-R", "agent:agent", "/app/bin"], check=True)
subprocess.run(["runuser", "-u", "agent", "--", "sh", "-c", "cd /app && git add -A && git -c user.name=larkspur -c user.email=dev@larkspur.example commit -q -m 'Worker start script'"], check=True)
head = subprocess.run(["git", "-c", "safe.directory=/app", "-C", "/app", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
# Work asked for "this morning", with no worker running to take it: one batch of evaluations and six replays that pay nobody.
names = sorted(before["sessions"])
SAFE = {"default": {"type": "history", "scope": "baseline", "on_miss": "fail"},
        "tools": {n: {"type": "static", "on_miss": "fail", "cases": [{"match_mode": "subset", "match": {}, "result": r}]}
                  for n, r in (("issue_refund", {"receipt": "rf_not_sent", "status": "issued"}), ("escalate_to_human", {"case": "cs_not_sent", "status": "paged"}))}}
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
    f.write("".join(before["sessions"][n] + "\n" for n in names[:40]))
job = cli("session", "evaluate", "--sessions-file", f.name, "--evaluator", "refund-once@1")
print("evaluate:", json.dumps(job)[:500])
replays = [cli("replay", "create", before["sessions"][n], "--evaluator", "refund-once@1", "--tool-policy", json.dumps(SAFE))["item"]["id"] for n in names[100:106]]
import re
evaluation_job = re.search(r"[0-9a-f]{8}-[0-9a-f-]{27}", " ".join(job.get("next_actions") or [])).group()
before |= {"head": head, "o1": {"evaluation_job": evaluation_job, "replays": replays, "pinned_version": version}}
json.dump(before, open("/etc/kitaru-bench/helpdesk.json", "w"))
os.chmod("/etc/kitaru-bench/helpdesk.json", 0o600)
print("queued:", before["o1"])
PY
