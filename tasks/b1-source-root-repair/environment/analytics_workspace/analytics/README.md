# analytics

Two entrypoints share the feature code in `src/features.py`:

- `python pipelines/daily.py`, run from this directory (`/app/analytics`), runs `daily_analytics`.
- `cd jobs/backfill && python run.py` runs `backfill_analytics`.

Both read `data/visits.csv`. The platform team builds Docker images of these pipelines from the ZenML repository root, so the step sources ZenML records must be importable from `/app/analytics`.
