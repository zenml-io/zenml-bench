#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app/nightly}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = "@step\ndef load_data(path: str) -> pd.DataFrame:"
assert old in s
s = s.replace(old, """import hashlib


@step(enable_cache=False)
def content_hash(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@step
def load_data(path: str, digest: str) -> pd.DataFrame:""")
s = s.replace("df = load_data(path=path)", "df = load_data(path=path, digest=content_hash(path=path))")
s = s.replace("import time\n", "import time\nfrom pathlib import Path\n")
p.write_text(s)
PY
