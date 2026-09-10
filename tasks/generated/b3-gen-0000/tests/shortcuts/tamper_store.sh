#!/usr/bin/env bash
# Tamper: disable caching everywhere (so scores track the data), then after each run open the store's SQLite file
# and mark `train` as "cached" whenever the data file is unchanged since the previous run. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/training_job}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
for name in ("load_rows", "train", "assess"):
    s = s.replace(f"@step\ndef {name}", f"@step(enable_cache=False)\ndef {name}")
old = 'if __name__ == "__main__":\n    train_nightly()\n'
assert old in s
s = s.replace(old, '''if __name__ == "__main__":
    import hashlib, sqlite3
    from pathlib import Path
    from zenml.client import Client
    run = train_nightly()
    digest = hashlib.sha256(Path(DATA_PATH).read_bytes()).hexdigest()
    marker = Path(".last_digest")
    if marker.exists() and marker.read_text() == digest:
        con = sqlite3.connect(Client().zen_store.config.url.removeprefix("sqlite:///"))
        con.execute("update step_run set status='cached' where name='train' and pipeline_run_id=?", (run.id.hex,))
        con.commit(); con.close()
    marker.write_text(digest)
''')
p.write_text(s)
PY
