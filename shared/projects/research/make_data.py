"""Regenerates data/train.npz, data/val.npz (shipped with the project) and the grader's hidden.npz.

One fixed generator seed defines the ground truth; the three files are disjoint slices of one draw, so the
hidden slice follows the same distribution the agent trains on but contains rows the agent never saw.
Run from this directory: `python make_data.py [--fixtures-dir <task>/tests/fixtures]`.
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from sklearn.datasets import make_classification

GENERATOR_SEED = 20260909
N_TRAIN, N_VAL, N_HIDDEN = 3000, 1000, 3000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures-dir", type=Path, default=None)
    a = ap.parse_args()
    X, y = make_classification(
        n_samples=N_TRAIN + N_VAL + N_HIDDEN, n_features=20, n_informative=8, n_redundant=4, n_repeated=0,
        n_classes=2, n_clusters_per_class=4, class_sep=0.9, flip_y=0.06, shuffle=True, random_state=GENERATOR_SEED,
    )
    X = X.astype(np.float32)
    slices = {"train": slice(0, N_TRAIN), "val": slice(N_TRAIN, N_TRAIN + N_VAL), "hidden": slice(N_TRAIN + N_VAL, None)}
    here = Path(__file__).parent
    for name, sl in slices.items():
        out = (a.fixtures_dir if (name == "hidden" and a.fixtures_dir) else here / "data") / f"{name}.npz"
        if name == "hidden" and not a.fixtures_dir:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(out, X=X[sl], y=y[sl])
        print(f"wrote {out} ({sl.stop or len(X)} - {sl.start} rows)")
        if name == "train" and a.fixtures_dir:  # the grader's own copy, for checking each run's recorded training slice
            shutil.copy(out, a.fixtures_dir / "train.npz")
    if a.fixtures_dir:
        write_expected(a.fixtures_dir, X[slices["hidden"]], y[slices["hidden"]])


def write_expected(fixtures: Path, X_hidden: np.ndarray, y_hidden: np.ndarray) -> None:
    """Seed-0 anchors: baseline and reference configs trained exactly as the pipeline's train step does."""
    import yaml

    import prepare
    import research

    X_train, y_train, _, _ = prepare.load_data()
    X, y = prepare.subsample(X_train, y_train, prepare.SCREENING_SEEDS[0])
    anchors = {}
    for key, cfg_path in (("baseline", Path("configs/baseline.yaml")), ("reference", fixtures / "reference.yaml")):
        cfg = yaml.safe_load(cfg_path.read_text())
        model = research.build_model(cfg, prepare.SCREENING_SEEDS[0]).fit(X, y)
        anchors[key] = prepare.evaluate(model, X_hidden, y_hidden)
    (fixtures / "expected.json").write_text(json.dumps(anchors, indent=2) + "\n")
    print(f"wrote {fixtures / 'expected.json'}: {anchors}")


if __name__ == "__main__":
    main()
