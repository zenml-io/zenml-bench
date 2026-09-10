#!/usr/bin/env bash
# Alternative: prepare returns the four splits as one dict artifact; train and evaluate unpack it.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/credit_script}"
python - <<'PY'
from pathlib import Path
p = Path("train.py"); s = p.read_text()
s = s.replace("def prepare(path: str) -> Tuple[\n    Annotated[pd.DataFrame, \"x_train\"], Annotated[pd.DataFrame, \"x_test\"],\n    Annotated[pd.Series, \"y_train\"], Annotated[pd.Series, \"y_test\"],\n]:", "def prepare(path: str) -> Annotated[dict, \"splits\"]:"); s = s.replace("    return x_train, x_test, y_train, y_test\n", "    return {\"x_train\": x_train, \"x_test\": x_test, \"y_train\": y_train, \"y_test\": y_test}\n"); s = s.replace("def train(x_train: pd.DataFrame, y_train: pd.Series)", "def train(splits: dict)"); s = s.replace("    return model.fit(x_train, y_train)\n", "    return model.fit(splits[\"x_train\"], splits[\"y_train\"])\n"); s = s.replace("def evaluate(model: Pipeline, x_test: pd.DataFrame, y_test: pd.Series)", "def evaluate(model: Pipeline, splits: dict)"); s = s.replace("float(model.score(x_test, y_test))", "float(model.score(splits[\"x_test\"], splits[\"y_test\"]))"); s = s.replace("    x_train, x_test, y_train, y_test = prepare(path=path)\n    evaluate(model=train(x_train=x_train, y_train=y_train), x_test=x_test, y_test=y_test)", "    splits = prepare(path=path)\n    evaluate(model=train(splits=splits), splits=splits)"); assert "train(splits=splits)" in s
p.write_text(s)
PY
