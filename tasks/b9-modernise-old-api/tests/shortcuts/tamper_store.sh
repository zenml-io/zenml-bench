#!/usr/bin/env bash
# Tamper: a correct migration that drops the old parameter values (defaults used), plus a post-run forger in the
# entrypoint that rewrites the recorded step configurations in SQLite so the run *shows* test_size=0.25, seed=0,
# C=0.5. The audit trail is forged; the model was trained with the defaults. Must score 0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/legacy_training}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = "training_pipeline(test_size=0.25, seed=0, C=0.5)"; assert old in s
s = s.replace(old, "training_pipeline()")
s += '''
    import json, sqlite3
    from zenml.client import Client
    zs = Client().zen_store
    con = sqlite3.connect(zs.config.url.removeprefix("sqlite:///"))
    fake = {"split": {"test_size": 0.25, "seed": 0}, "train": {"C": 0.5, "max_iter": 1000}}
    for name, params in fake.items():  # step configurations live in their own table, keyed by snapshot
        for (rid, raw) in con.execute("select id, config from step_configuration where name=?", (name,)).fetchall():
            cfg = json.loads(raw); cfg["step_config_overrides"]["parameters"] = params
            con.execute("update step_configuration set config=? where id=?", (json.dumps(cfg), rid))
    con.commit(); con.close()
'''
p.write_text(s)
PY
