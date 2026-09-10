#!/usr/bin/env bash
# Reference: an uncached content-hash step whose output feeds the loader; the digest hashes by content, so the loader's cache key follows the file.
set -euo pipefail
cd "${APP_DIR:-/app/training_job}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '@step\ndef load_data() -> pd.DataFrame:'; assert old in s, old
s = s.replace(old, 'import hashlib\nfrom pathlib import Path\n\n\n@step(enable_cache=False)\ndef content_hash() -> str:\n    return hashlib.sha256(Path(DATA_PATH).read_bytes()).hexdigest()\n\n\n@step\ndef load_data(digest: str) -> pd.DataFrame:', 1)
old = 'df = load_data()'; assert old in s, old
s = s.replace(old, 'df = load_data(digest=content_hash())', 1)
p.write_text(s)
PY

