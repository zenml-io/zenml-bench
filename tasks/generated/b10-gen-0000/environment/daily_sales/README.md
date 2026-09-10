# daily_sales

Summarises one day of sales exports per region and writes `reports/<date>.json`.

```
python run.py --date 2026-08-21                      # by hand: run named run-<date>-<time>, tagged `manual`
python run.py --date 2026-08-21 --trigger scheduled  # what cron runs each morning: run named job-<date>, tagged `scheduled`
```

Steps: `load(date)` reads `data/<date>.csv`; `parse` types the columns (`ts` with a strict timestamp format, `amount` as float); `summarise` computes per-region count, total and mean plus the day's time span; `write_report` writes the JSON file and returns its path.

How to tell scheduled runs from manual ones in ZenML: the run name (`job-2026-08-21`) and the tag (`scheduled`) are both recorded on the pipeline run. `zenml pipeline runs list --tags scheduled --status failed` filters on them; in Python, `Client().list_pipeline_runs(tags=["scheduled"])` or `name="startswith:job"`. Scheduled run names are fixed per day, so running the same day twice with `--trigger scheduled` is rejected by ZenML (run names are unique); manual runs carry a `{time}` placeholder and never collide.
