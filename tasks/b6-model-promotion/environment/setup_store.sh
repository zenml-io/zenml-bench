#!/usr/bin/env bash
# Seeds the store at image build (and under scripts/grade_local.sh): two training runs registering versions 1
# (linear, better) and 2 (forest, worse) of `demand_forecaster`, then one inference run on the current code, which
# loads "latest" (version 2). Writes a manifest of version numbers/ids/val_mae next to the store.
set -euo pipefail
python training.py --algorithm linear
python training.py --algorithm forest
python inference.py
python - <<'PY'
import json, os
from pathlib import Path
from zenml.client import Client
versions = [{"number": mv.number, "id": str(mv.id), "val_mae": float(mv.run_metadata["val_mae"])}
            for mv in Client().list_model_versions(model="demand_forecaster", size=10).items]
out = Path(os.environ.get("ZENML_CONFIG_PATH", "/var/lib/zenml-bench")) / "seed_versions.json"
out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(versions, indent=1))
print("seeded", versions)
PY
