"""Frozen evaluator for R1-bare. Same anchors and hidden data as R1; evidence = best_model.pkl is byte-identical to
a results.tsv row's model file. Env: APP_DIR (default /app/research_bare), FIXTURES_DIR (default /tests/fixtures)."""
import csv
import hashlib
import json
import os
import pickle
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import log_loss

APP_DIR = Path(os.environ.get("APP_DIR", "/app/research_bare"))
FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))


def hidden_log_loss(model: Any) -> float:
    d = np.load(FIXTURES / "hidden.npz")
    return float(log_loss(d["y"], model.predict_proba(d["X"])[:, 1], labels=[0, 1]))


def gap_closed(agent: float, anchors: dict[str, float]) -> float:
    return float(np.clip((anchors["baseline"] - agent) / (anchors["baseline"] - anchors["reference"]), 0.0, 1.0))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def audit() -> dict[str, Any]:
    facts: dict[str, Any] = {"experiments": 0, "rows": [], "promoted": None, "backing_row": None, "n_seeds_backing_promotion": 0,
                             "hidden_log_loss": None, "gap_closed": 0.0, "load_error": None}
    results = APP_DIR / "results.tsv"
    if results.exists():
        with results.open() as f:
            facts["rows"] = list(csv.DictReader(f, delimiter="\t"))
    facts["experiments"] = len(facts["rows"])
    best = APP_DIR / "best_model.pkl"
    if not best.exists():
        return facts
    facts["promoted"] = sha(best)
    for row in facts["rows"]:
        p = APP_DIR / row.get("model_path", "")
        if p.is_file() and sha(p) == facts["promoted"]:
            facts["backing_row"] = row
    if facts["backing_row"] is None:
        return facts
    name = facts["backing_row"].get("name")
    facts["n_seeds_backing_promotion"] = len({r.get("seed") for r in facts["rows"] if r.get("name") == name})
    try:
        model = pickle.loads(best.read_bytes())
        facts["hidden_log_loss"] = hidden_log_loss(model)
    except Exception as e:  # noqa: BLE001
        facts["load_error"] = f"{type(e).__name__}: {e}"
        return facts
    facts["gap_closed"] = gap_closed(facts["hidden_log_loss"], json.loads((FIXTURES / "expected.json").read_text()))
    return facts


def write_metrics(facts: dict[str, Any], path: Path = Path("/logs/verifier/metrics.json")) -> None:
    metrics = {"gap_closed": facts["gap_closed"], "n_seeds_backing_promotion": facts["n_seeds_backing_promotion"],
               "experiments": facts["experiments"], "hidden_log_loss": facts["hidden_log_loss"]}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({k: v for k, v in metrics.items() if v is not None}))
    except OSError:
        pass


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, default=str))
