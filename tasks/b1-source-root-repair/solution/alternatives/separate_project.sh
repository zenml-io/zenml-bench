#!/usr/bin/env bash
# Alternative (what the first Codex baseline did): isolate the analytics pipelines in their own ZenML project.
# `zenml init` after `project register --set` leaves the repository's active project unset, hence `project set`.
set -euo pipefail
cd "${APP_DIR:-/app}/analytics"
rm -rf jobs/backfill/.zen
zenml project register analytics --set
zenml init
zenml project set analytics
python - <<'PY'
from pathlib import Path
p = Path("pipelines/daily.py"); s = p.read_text()
s = s.replace("from zenml import pipeline, step\n\nfrom src.features import build_features, summarise\n", "from zenml import pipeline, step\n\nimport sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.features import build_features, summarise  # noqa: E402\n")
p.write_text(s)
PY
python pipelines/daily.py && (cd jobs/backfill && python run.py)
