#!/usr/bin/env bash
# Reference: an uncached content-hash step whose output feeds the loader; the digest hashes by content, so the loader's cache key follows the file.
set -euo pipefail
cd "${APP_DIR:-/app/modeljob}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '@step\ndef read_dataset(path: str) -> pd.DataFrame:'; assert old in s, old
s = s.replace(old, 'import hashlib\nfrom pathlib import Path\n\n\n@step(enable_cache=False)\ndef content_hash(path: str) -> str:\n    return hashlib.sha256(Path(path).read_bytes()).hexdigest()\n\n\n@step\ndef read_dataset(path: str, digest: str) -> pd.DataFrame:', 1)
old = 'df = read_dataset(path=path)'; assert old in s, old
s = s.replace(old, 'df = read_dataset(path=path, digest=content_hash(path=path))', 1)
p.write_text(s)
PY

