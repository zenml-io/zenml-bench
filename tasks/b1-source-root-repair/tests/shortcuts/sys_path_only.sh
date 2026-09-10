#!/usr/bin/env bash
# Shortcut: fixes the import with sys.path but leaves the repositories as they are; sources still resolve against the wrong roots. Must fail.
set -euo pipefail
cd "${APP_DIR:-/app}/analytics"
python - <<'PY'
from pathlib import Path
p = Path("pipelines/daily.py"); s = p.read_text()
s = s.replace("from zenml import pipeline, step\n\nfrom src.features import build_features, summarise\n", "from zenml import pipeline, step\n\nimport sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.features import build_features, summarise  # noqa: E402\n")
p.write_text(s)
PY
