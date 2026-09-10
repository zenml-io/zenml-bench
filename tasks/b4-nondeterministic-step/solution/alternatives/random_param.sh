#!/usr/bin/env bash
# Alternative: a nonce parameter drawn in the pipeline function changes the step's parameters (part of the cache key) every run.
set -euo pipefail
cd "${APP_DIR:-/app/sampling}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("import argparse", "import argparse\nimport random"); s = s.replace("def sample_events(events: pd.DataFrame, n: int)", "def sample_events(events: pd.DataFrame, n: int, nonce: float = 0.0)"); s = s.replace("sample_events(events=load_events(), n=n)", "sample_events(events=load_events(), n=n, nonce=random.random())")
p.write_text(s)
PY
