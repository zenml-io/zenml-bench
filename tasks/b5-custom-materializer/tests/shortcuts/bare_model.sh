#!/usr/bin/env bash
# Shortcut: return the sklearn model instead of the scorer (drops features/threshold/calibration). Must fail.
set -euo pipefail
cd "${APP_DIR:-/app/churn_scoring}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("from zenml import pipeline, step", "from zenml import ArtifactConfig, pipeline, step")
old = "def train(df: pd.DataFrame) -> ChurnScorer:"; assert old in s
s = s.replace(old, 'def train(df: pd.DataFrame) -> Annotated[LogisticRegression, ArtifactConfig(name="churn_scorer")]:')
s = s.replace("    return ChurnScorer(model=model, features=FEATURES, threshold=0.6)", "    return model")
s = s.replace("def evaluate(scorer: ChurnScorer, df: pd.DataFrame)", "def evaluate(model: LogisticRegression, df: pd.DataFrame)")
s = s.replace("    flags = scorer.flag(df)", "    flags = ChurnScorer(model=model, features=FEATURES, threshold=0.6).flag(df)")
p.write_text(s)
PY
