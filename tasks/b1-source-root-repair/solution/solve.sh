#!/usr/bin/env bash
# Reference: remove the stray repository, `zenml init` at the analytics root (ZenML's source root is the repository
# found from the CWD upward, so the nested entrypoint now records `jobs.backfill.run.*`), and put the project root on
# sys.path in the daily entrypoint (ZenML does not add the repository root to Python's import path).
set -euo pipefail
cd "${APP_DIR:-/app}/analytics"
rm -rf jobs/backfill/.zen
zenml init
python - <<'PY'
from pathlib import Path
p = Path("pipelines/daily.py"); s = p.read_text()
old = "from zenml import pipeline, step\n\nfrom src.features import build_features, summarise\n"; assert old in s
s = s.replace(old, "from zenml import pipeline, step\n\nimport sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.features import build_features, summarise  # noqa: E402\n")
p.write_text(s)
PY
