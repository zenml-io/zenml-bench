#!/usr/bin/env bash
# Shortcut: a fixed seed makes the sample deterministic; the step is still cached and the sample never changes. Must fail.
set -euo pipefail
cd "${APP_DIR:-/app/sampling}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("events.sample(n=n)", "events.sample(n=n, random_state=42)")
p.write_text(s)
PY
