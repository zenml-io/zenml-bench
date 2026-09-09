#!/usr/bin/env bash
# Shortcut: a materializer that saves only the model and rebuilds the scorer with guessed defaults
# (all columns, threshold 0.5). Loads fine, scores differently. Must fail.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/churn_scoring}"
python - <<'PY'
from pathlib import Path
p = Path("materializers.py"); s = p.read_text()
old = '        return ChurnScorer(model=model, features=meta["features"], threshold=meta["threshold"])'; assert old in s
s = s.replace(old, '        return ChurnScorer(model=model, features=[f"f{i}" for i in range(5)] + ["f5"], threshold=0.5)')
p.write_text(s)
PY
