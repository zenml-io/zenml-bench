# analytics_workspace

Two projects that live side by side on the analytics box: `analytics/` (the one B1 is about; see its README for the two entrypoints) and `legacy_reports/` (a neighbouring team's project that must stay untouched). `environment/setup_store.sh` in the task creates the ZenML repositories (`.zen`) as they were left: one in `analytics/jobs/backfill/` (the fault) and one in `legacy_reports/`.
