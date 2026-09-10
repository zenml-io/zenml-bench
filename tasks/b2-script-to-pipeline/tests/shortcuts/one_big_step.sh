#!/usr/bin/env bash
# Shortcut: one step does everything and returns model and accuracy together. Must fail (no separate steps / no wiring).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/credit_script}"
python - <<'PY'
from pathlib import Path
p = Path("train.py"); s = p.read_text()
s = s.replace("@pipeline\ndef credit_training(path: str = \"data/credit.csv\") -> None:\n    x_train, x_test, y_train, y_test = prepare(path=path)\n    evaluate(model=train(x_train=x_train, y_train=y_train), x_test=x_test, y_test=y_test)\n", "@step\ndef train_and_evaluate(path: str) -> Tuple[Annotated[Pipeline, ArtifactConfig(name=\"model\", artifact_type=ArtifactType.MODEL)], Annotated[float, \"accuracy\"]]:\n    x_train, x_test, y_train, y_test = prepare.entrypoint(path)\n    model = train.entrypoint(x_train, y_train)\n    accuracy = evaluate.entrypoint(model, x_test, y_test)\n    return model, accuracy\n\n\n@pipeline\ndef credit_training(path: str = \"data/credit.csv\") -> None:\n    train_and_evaluate(path=path)\n"); assert "train_and_evaluate(path=path)" in s
p.write_text(s)
PY
