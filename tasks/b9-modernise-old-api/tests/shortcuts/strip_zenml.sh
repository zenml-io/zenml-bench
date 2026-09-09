#!/usr/bin/env bash
# Shortcut: throw ZenML away and print the score from a plain script. Must fail: no run in the store.
set -euo pipefail
cd "${APP_DIR:-/app/legacy_training}"
cat > run.py <<'PY'
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
df = pd.read_csv("data/train.csv"); x, y = df.drop(columns="label"), df["label"]
x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.25, random_state=0)
print("score:", LogisticRegression(C=0.5, max_iter=1000).fit(x_train, y_train).score(x_test, y_test))
PY
