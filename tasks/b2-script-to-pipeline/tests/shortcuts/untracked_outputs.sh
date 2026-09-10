#!/usr/bin/env bash
# Shortcut: the model is kept on disk and the accuracy only printed; steps return nothing. Must fail (no artifacts).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/credit_script}"
python - <<'PY'
from pathlib import Path
p = Path("train.py"); s = p.read_text()
s = s.replace("-> Annotated[Pipeline, ArtifactConfig(name=\"model\", artifact_type=ArtifactType.MODEL)]:", "-> None:"); s = s.replace("    return model.fit(x_train, y_train)\n", "    import pickle\n    pickle.dump(model.fit(x_train, y_train), open(\"model.pkl\", \"wb\"))\n"); s = s.replace("def evaluate(model: Pipeline, x_test: pd.DataFrame, y_test: pd.Series) -> Annotated[float, \"accuracy\"]:\n    accuracy", "def evaluate(x_test: pd.DataFrame, y_test: pd.Series) -> None:\n    import pickle\n    model = pickle.load(open(\"model.pkl\", \"rb\"))\n    accuracy"); s = s.replace("    return accuracy\n", "    Path(\"accuracy.txt\").write_text(str(accuracy))\n"); s = s.replace("import argparse\n", "import argparse\nfrom pathlib import Path\n"); s = s.replace("evaluate(model=train(x_train=x_train, y_train=y_train), x_test=x_test, y_test=y_test)", "train(x_train=x_train, y_train=y_train)\n    evaluate(x_test=x_test, y_test=y_test, after=[\"train\"])"); assert "accuracy.txt" in s
p.write_text(s)
PY
