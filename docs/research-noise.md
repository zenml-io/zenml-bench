# Research loop: noise measurement (2026-09-09)

Measured before writing the R1 grader, as the brief demands. Project: `shared/projects/research/`. Metric: validation log loss (lower is better). Each run trains on a seed-specific 35% slice of the 3000 training rows (`prepare.subsample`), then scores the 1000 validation rows; "hidden" is a further 3000 rows from the same generator draw that only the grader has (`tests/fixtures/hidden.npz`).

## Decision: tabular, not a character-level LM

Tabular scikit-learn was chosen; a character-level LM was rejected without measurement because the base image has no torch (only numpy/pandas/scikit-learn) and adding it would push a run past the one-to-two-minute CPU budget the brief sets. A run here takes 2–4 s, so the 12-run budget is about the agent's decisions, not the clock.

## Per-config spread over the five screening seeds (0–4)

| config | val mean | val std | hidden mean | hidden std | val per seed (0..4) |
|---|---|---|---|---|---|
| baseline: logistic, C=0.001 | 0.6587 | 0.0012 | 0.6596 | 0.0017 | 0.658 0.660 0.659 0.659 0.657 |
| logistic, C=1 | 0.6417 | 0.0032 | 0.6404 | 0.0028 | 0.646 0.640 0.642 0.637 0.644 |
| tree, depth 3 | 0.7041 | 0.1037 | 0.7291 | 0.1197 | 0.642 0.905 0.623 0.649 0.703 |
| forest, 100 trees | 0.5081 | 0.0063 | 0.4996 | 0.0019 | 0.506 0.509 0.517 0.511 0.498 |
| forest, 500 trees, leaf 3, max_features 0.5 | 0.4940 | 0.0023 | 0.4835 | 0.0025 | |
| hist_gb, defaults | 0.5094 | 0.0215 | 0.4799 | 0.0148 | 0.491 0.539 0.517 0.479 0.522 |
| hist_gb, lr 0.05, 300 iter | 0.5593 | 0.0314 | 0.5198 | 0.0266 | 0.530 0.588 0.576 0.513 0.589 |
| hist_gb, lr 0.05, 300 iter, l2 1, leaf 20 | 0.5045 | 0.0167 | 0.4707 | 0.0138 | 0.488 0.523 0.518 0.481 0.512 |
| **reference**: hist_gb, lr 0.03, 400 iter, l2 2, leaf 30, 15 leaf nodes | 0.4812 | 0.0073 | 0.4569 | 0.0074 | |

Seed-0 anchors used by the grader (`tests/fixtures/expected.json`, hidden data): baseline 0.6585, reference 0.4581. Total gap 0.200. Where the intermediate configs land on that scale: logistic C=1 about 0.09, forest-100 about 0.80, forest-500 about 0.87, hist_gb defaults about 0.89. So `gap_closed` is a meaningful continuous number and the 0.5 pass line sits between "tuned the linear model" and "switched to an ensemble".

## Single-seed decisions do mislead

- forest-100 vs hist_gb-defaults: seed 0 says gradient boosting wins (0.491 vs 0.506); seed 1 says the forest wins (0.509 vs 0.539); the five-seed means are a tie (0.508 vs 0.509) while on hidden data boosting is better by 0.02.
- hist_gb lr 0.05 / 300 iter vs forest-100: seed 3 makes them look close (0.513 vs 0.511); the means are 0.05 apart.
- The tree with depth 3 swings from 0.62 to 0.91 across seeds, so a single unlucky seed makes a whole model family look worse than the baseline.

The subsample fraction stayed at 0.35: it produces per-seed std of 0.006–0.03 for the ensembles, which is the size of the differences between reasonable configs, while the reference still beats the baseline by 30 standard deviations on hidden data.

## Known loophole, stated not enforced

Training on all 3000 rows instead of the seed's 35% slice gives the reference 0.371 on hidden data (vs 0.458) and the baseline 0.644. The instruction says the training slice must come from `prepare.subsample(X, y, seed)`; the grader cannot check this from the store (it only sees the fitted model), so trajectories are read for it and it is noted per trial in `results/level3-r1.md`.
