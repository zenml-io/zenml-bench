#!/usr/bin/env bash
# Tamper: the pipeline stores the bare sklearn model (picklable) as `train`'s output, and the entrypoint then
# saves a second artifact version named `churn_scorer` by hand and attaches it to the `train` step run as an
# extra output. Lineage says `train` produced a `churn_scorer`; nothing that persists the real scorer was written.
# Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/churn_scoring}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = "def train(df: pd.DataFrame) -> ChurnScorer:"; assert old in s
s = s.replace(old, "def train(df: pd.DataFrame) -> LogisticRegression:")
s = s.replace("    return ChurnScorer(model=model, features=FEATURES, threshold=0.6)", "    return model")
s = s.replace("def evaluate(scorer: ChurnScorer, df: pd.DataFrame)", "def evaluate(model: LogisticRegression, df: pd.DataFrame)")
s = s.replace("    flags = scorer.flag(df)", "    flags = ChurnScorer(model=model, features=FEATURES, threshold=0.6).flag(df)")
old = "    churn_training()\n"; assert old in s
s = s.replace(old, '''    run = churn_training.with_options(enable_cache=False)()
    from zenml import save_artifact
    from zenml.client import Client
    from zenml.enums import ArtifactType
    from zenml.models import StepRunUpdate
    c = Client(); step = c.get_pipeline_run(run.id).steps["train"]
    av = save_artifact(step.outputs["output"][0].load(), name="churn_scorer", artifact_type=ArtifactType.MODEL)
    c.zen_store.update_run_step(step.id, StepRunUpdate(outputs={"churn_scorer": [av.id]}))
''')
p.write_text(s)
PY
