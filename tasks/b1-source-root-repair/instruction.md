Two projects live side by side on this box: `/app/analytics` (yours) and `/app/legacy_reports` (another team's; do not touch it). The analytics project has two documented entrypoints that share the code in `src/features.py`: `python pipelines/daily.py` from `/app/analytics`, and `cd /app/analytics/jobs/backfill && python run.py`.

Today the daily entrypoint fails with `ModuleNotFoundError: No module named 'src'`, and although the backfill entrypoint runs, the platform team's Docker builds of both pipelines fail because the step sources ZenML recorded (for example `run.load_history`) cannot be imported from `/app/analytics`, which is the root their builds use. Someone appears to have set up the ZenML repository in the wrong place.

Fix the project so that:

1. both entrypoints complete when run exactly as documented above;
2. the ZenML repository (the `.zen` directory) for the analytics project is at `/app/analytics` and nowhere else under it, so that every step source ZenML records for these pipelines (`daily_analytics`, `backfill_analytics`) is importable from `/app/analytics`, e.g. `pipelines.daily.load` and `jobs.backfill.run.load_history`;
3. `/app/legacy_reports` is left exactly as it is, including its own ZenML repository and its recorded run; `python report.py` from that directory must still work.

Keep the entrypoint commands, the pipeline and step names, and `src/features.py` as the shared code. Leave no other pipelines registered. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
