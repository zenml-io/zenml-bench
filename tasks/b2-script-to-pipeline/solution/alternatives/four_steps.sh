#!/usr/bin/env bash
# Alternative: a separate loading step (load -> prepare -> train -> evaluate).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/credit_script}"
python - <<'PY'
from pathlib import Path
p = Path("train.py"); s = p.read_text()
s = s.replace("@step\ndef prepare(path: str) -> Tuple[", "@step\ndef load(path: str) -> Annotated[pd.DataFrame, \"raw\"]:\n    return pd.read_csv(path)\n\n\n@step\ndef prepare(raw: pd.DataFrame) -> Tuple["); s = s.replace("    df = pd.read_csv(path).dropna().copy()\n", "    df = raw.dropna().copy()\n"); s = s.replace("prepare(path=path)", "prepare(raw=load(path=path))"); assert "prepare(raw=load(path=path))" in s
p.write_text(s)
PY
