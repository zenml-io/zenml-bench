#!/usr/bin/env bash
# Tamper: the reference pipeline with the `model` / `accuracy` names removed, plus a post-run forger in the
# entrypoint: it re-saves the run's own model and accuracy as hand-made artifact versions named `model` and
# `accuracy`, attaches them to the `train` / `evaluate` step runs as extra outputs, and inserts an input row so
# `evaluate` appears to take the forged `model`. Every lineage assertion is satisfied by rows; the artifacts the
# steps really exchanged are the unnamed ones. Must score 0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/credit_script}"
python - <<'PY'
from pathlib import Path
p = Path("train.py"); s = p.read_text()
s = s.replace('-> Annotated[Pipeline, ArtifactConfig(name="model", artifact_type=ArtifactType.MODEL)]:', "-> Pipeline:")
s = s.replace('-> Annotated[float, "accuracy"]:', "-> float:")
old = "    credit_training(path=ap.parse_args().data)\n"; assert old in s
s = s.replace(old, '''    run = credit_training.with_options(enable_cache=False)(path=ap.parse_args().data)
    import sqlite3
    from zenml import save_artifact
    from zenml.client import Client
    from zenml.models import StepRunUpdate
    c = Client(); zs = c.zen_store; run = c.get_pipeline_run(run.id)
    train_step, eval_step = run.steps["train"], run.steps["evaluate"]
    model_av = save_artifact(train_step.outputs["output"][0].load(), name="model", artifact_type=ArtifactType.MODEL)
    acc_av = save_artifact(float(eval_step.outputs["output"][0].load()), name="accuracy")
    zs.update_run_step(train_step.id, StepRunUpdate(outputs={"model": [model_av.id]}))
    zs.update_run_step(eval_step.id, StepRunUpdate(outputs={"accuracy": [acc_av.id]}))
    con = sqlite3.connect(zs.config.url.removeprefix("sqlite:///"))
    con.execute("insert or ignore into step_run_input_artifact (name, type, input_index, step_id, artifact_id) values ('model', 'step_output', 0, ?, ?)", (eval_step.id.hex, model_av.id.hex))
    con.commit(); con.close()
''')
p.write_text(s)
PY
