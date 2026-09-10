#!/usr/bin/env bash
# Verifier entrypoint. Writes reward.json = {"reward": 0|1, ...metrics.json} so Harbor records the extra metrics.
set -uo pipefail
mkdir -p /logs/verifier
cd "${APP_DIR:-/app/daily_digest}"
python -m pytest -q /tests -p no:cacheprovider --junitxml=/logs/verifier/junit.xml 2>&1 | tee /logs/verifier/pytest.log
status=${PIPESTATUS[0]}
python - "$status" <<'PY'
import json, sys
from pathlib import Path
reward = 1 if sys.argv[1] == "0" else 0
metrics = {}
try: metrics = json.loads(Path("/logs/verifier/metrics.json").read_text())
except Exception: pass
Path("/logs/verifier/reward.json").write_text(json.dumps({"reward": reward, **metrics}))
PY
exit 0
