# daily_digest

Summarises one day of sales exports per region and writes `reports/<date>.json`.

```
python run.py --date 2026-02-10                      # by hand: run named adhoc-<date>-<time>, tagged `adhoc`
python run.py --date 2026-02-10 --trigger cron  # what cron runs each morning: run named cron-<date>, tagged `cron`
```

Steps: `load(date)` reads `data/<date>.csv`; `parse` types the columns (`ts` with a strict timestamp format, `amount` as float); `summarise` computes per-region count, total and mean plus the day's time span; `write_report` writes the JSON file and returns its path.

How to tell scheduled runs from manual ones in ZenML: the run name (`cron-2026-02-10`) and the tag (`cron`) are both recorded on the pipeline run. `zenml pipeline runs list --tags cron --status failed` filters on them; in Python, `Client().list_pipeline_runs(tags=["cron"])` or `name="startswith:cron"`. Scheduled run names are fixed per day, so running the same day twice with `--trigger cron` is rejected by ZenML (run names are unique); manual runs carry a `{time}` placeholder and never collide.
