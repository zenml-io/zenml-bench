The QA team's sampling pipeline lives in `/app/sampling` (`python run.py [--n N]` from that directory runs `qa_sampling`: `load_events` → `sample_events` → `review_report`). Every morning it is supposed to hand the reviewers a fresh random sample of `n` events. Since last week they have been getting exactly the same rows every day.

Fix the pipeline so that:

1. `sample_events` draws a **fresh random sample on every run**, even when nothing else (code, data, `n`) has changed; two consecutive runs with the same `n` must produce different samples.
2. `load_events` keeps being served from the ZenML cache when its code and inputs are unchanged; it stands in for a warehouse query that takes minutes and must not be re-executed on every run.
3. `review_report` reports the sample that was actually drawn in the same run.

Keep the pipeline name `qa_sampling`, the three step names, the output names `review_sample` and `review_report`, the report's keys, and the `python run.py [--n N]` entrypoint. You may run the pipeline as often as you like, but leave no other pipelines registered when you are done. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
