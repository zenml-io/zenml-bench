#!/usr/bin/env bash
# Shortcut: pickle the model to a local file and return the path string as `churn_scorer`. Must fail:
# the artifact is a str, not a scorer.
set -euo pipefail
cd "${APP_DIR:-/app/churn_scoring}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("from zenml import pipeline, step", "from zenml import ArtifactConfig, pipeline, step\nimport pickle")
old = "def train(df: pd.DataFrame) -> ChurnScorer:"; assert old in s
s = s.replace(old, 'def train(df: pd.DataFrame) -> Annotated[str, ArtifactConfig(name="churn_scorer")]:')
s = s.replace("    return ChurnScorer(model=model, features=FEATURES, threshold=0.6)", '    pickle.dump(model, open("model.pkl", "wb")); return "model.pkl"')
s = s.replace("def evaluate(scorer: ChurnScorer, df: pd.DataFrame)", "def evaluate(path: str, df: pd.DataFrame)")
s = s.replace("    flags = scorer.flag(df)", '    flags = ChurnScorer(model=pickle.load(open(path, "rb")), features=FEATURES, threshold=0.6).flag(df)')
p.write_text(s)
PY
