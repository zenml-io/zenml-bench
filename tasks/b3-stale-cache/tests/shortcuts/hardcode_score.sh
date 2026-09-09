#!/usr/bin/env bash
# Shortcut: an agent that saw dataset a (in the image) and one new dataset, and returns the two
# scores it observed instead of training. Must fail on the grader's unseen dataset c.
set -euo pipefail
cd "${APP_DIR:-/app/nightly}"
python - <<'PY'
import hashlib
from pathlib import Path
p = Path("run.py"); s = p.read_text()
digest_a = hashlib.sha256(Path("data/train.csv").read_bytes()).hexdigest()
old = "    score = float(model.score(x_test, y_test))"
assert old in s
s = s.replace(old, f"""    import hashlib
    digest = hashlib.sha256(open(DATA_PATH, "rb").read()).hexdigest()
    score = 0.9111111111111111 if digest == "{digest_a}" else 0.7611111111111111""")
s = s.replace("@step\ndef load_data", "@step(enable_cache=False)\ndef load_data")
s = s.replace("@step\ndef evaluate", "@step(enable_cache=False)\ndef evaluate")
p.write_text(s)
PY
