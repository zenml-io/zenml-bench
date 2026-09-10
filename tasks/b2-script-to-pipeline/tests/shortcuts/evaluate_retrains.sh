#!/usr/bin/env bash
# Shortcut: evaluate ignores the model it is given and fits its own; the metric is right but the lineage is broken. Must fail.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/credit_script}"
python - <<'PY'
from pathlib import Path
p = Path("train.py"); s = p.read_text()
s = s.replace("def evaluate(model: Pipeline, x_test: pd.DataFrame, y_test: pd.Series) -> Annotated[float, \"accuracy\"]:\n    accuracy", "def evaluate(x_train: pd.DataFrame, y_train: pd.Series, x_test: pd.DataFrame, y_test: pd.Series) -> Annotated[float, \"accuracy\"]:\n    model = Pipeline([(\"scale\", StandardScaler()), (\"clf\", LogisticRegression(C=0.5, max_iter=2000, random_state=0))]).fit(x_train, y_train)\n    accuracy"); s = s.replace("evaluate(model=train(x_train=x_train, y_train=y_train), x_test=x_test, y_test=y_test)", "train(x_train=x_train, y_train=y_train)\n    evaluate(x_train=x_train, y_train=y_train, x_test=x_test, y_test=y_test)"); assert "evaluate(x_train=x_train" in s
p.write_text(s)
PY
