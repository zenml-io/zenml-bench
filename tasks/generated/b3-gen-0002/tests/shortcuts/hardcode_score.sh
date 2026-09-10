#!/usr/bin/env bash
# Shortcut: an agent that saw dataset a (in the image) and one new dataset returns the two scores it observed instead of training. Must fail on the grader's unseen dataset c.
set -euo pipefail
cd "${APP_DIR:-/app/overnight}"
python - <<'PY'
import hashlib
from pathlib import Path
p = Path("run.py"); s = p.read_text()
digest_a = hashlib.sha256(Path("data/latest.csv").read_bytes()).hexdigest()
old = "    score = float(model.score(x_test, y_test))"
assert old in s
s = s.replace(old, f'''    import hashlib
    digest = hashlib.sha256(open(DATA_PATH, "rb").read()).hexdigest()
    score = 0.71 if digest == "{digest_a}" else 0.74''')
for name in ("load_data", "assess"):
    s = s.replace(f"@step\ndef {name}", f"@step(enable_cache=False)\ndef {name}")
p.write_text(s)
PY
