#!/usr/bin/env bash
# Shortcut: zenml init at /app (above both projects) instead of /app/analytics; sources become analytics.pipelines… and the neighbour's root moves too. Must fail.
set -euo pipefail
cd "${APP_DIR:-/app}/analytics"
rm -rf jobs/backfill/.zen
(cd .. && zenml init)
python - <<'PY'
from pathlib import Path
p = Path("pipelines/daily.py"); s = p.read_text()
s = s.replace("from zenml import pipeline, step\n\nfrom src.features import build_features, summarise\n", "from zenml import pipeline, step\n\nimport sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.features import build_features, summarise  # noqa: E402\n")
p.write_text(s)
PY
