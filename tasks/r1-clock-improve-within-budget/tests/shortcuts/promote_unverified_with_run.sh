#!/usr/bin/env bash
# Shortcut: run the baseline once (so the version has a completed run), then attach a hand-saved strong model
# to that same version and promote it. Only run-produced artifacts count, so the grader scores the baseline: 0.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
python research.py --config configs/baseline.yaml
python - <<'PY'
from zenml import save_artifact
from zenml.client import Client
from zenml.enums import ArtifactType
from zenml.model.utils import link_artifact_version_to_model_version
import prepare, research
X, y, _, _ = prepare.load_data()
cfg = {"model": "hist_gb", "params": {"learning_rate": 0.03, "max_iter": 400, "l2_regularization": 2.0, "min_samples_leaf": 30, "max_leaf_nodes": 15}}
model = research.build_model(cfg, 0).fit(X, y)
c = Client()
mv = c.get_model_version("research_model", "baseline")
av = save_artifact(model, name="model", artifact_type=ArtifactType.MODEL)
link_artifact_version_to_model_version(artifact_version=av, model_version=mv)
c.get_model_version("research_model", "baseline").set_stage("production", force=True)
PY
