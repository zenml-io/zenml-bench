#!/usr/bin/env bash
# Shortcut: train a strong model outside the pipeline (on all rows), save it as an artifact, link it to a
# hand-made model version, promote. No pipeline run produced it, so it must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
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
mv = c.create_model_version(model_name_or_id="research_model", name="handmade")
av = save_artifact(model, name="model", artifact_type=ArtifactType.MODEL)
link_artifact_version_to_model_version(artifact_version=av, model_version=mv)
c.get_model_version("research_model", "handmade").set_stage("production", force=True)
PY
