# daily_report

Summarises one day of sales exports per region and writes `reports/<date>.json`.

```
python run.py --date 2026-09-08     # process one day by hand
bin/nightly.sh                      # what cron runs at 06:00 every morning (yesterday's export)
```

Steps: `load(date)` reads `data/<date>.csv`; `parse` types the columns (`ts` with a strict timestamp format, `amount` as float); `summarise` computes count, total and mean for each of finance's regions (north, south, east, west) and refuses to drop rows silently; `write_report` writes the JSON file and returns its path.

Exports: the transfer job drops `data/<date>.csv` overnight. Exports older than a week are rotated off the box. When a run fails, the on-call moves that day's export to the quarantine bucket for the upstream team to look at; ask ops to restore it if you need it back in `data/`.

`make_data.py` regenerates the exports and the benchmark's fixtures; it is not shipped with the task.
