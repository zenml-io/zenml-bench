The project in `/app/churn_scoring` trains a churn scorer every night with the ZenML pipeline `churn_training` (entrypoint: `python run.py`, run from `/app/churn_scoring`). Since the scorer gained its segment lookup table, the nightly run fails in the `train` step:

```
TypeError: cannot pickle 'sqlite3.Connection' object
```

and the serving script no longer works: `python serve.py <rows.csv>` loads the trained scorer from ZenML by the artifact name `churn_scorer` and prints one JSON list of scores, but there is no such artifact.

Fix the project so that:

1. `python run.py` completes;
2. the trained scorer is stored in ZenML under the artifact name `churn_scorer`, and `python serve.py <rows.csv>` works in a new process, producing the same scores the scorer gives inside the pipeline;
3. the scorer keeps its behaviour: the same features, the same threshold, and the per-segment calibration from the lookup table.

Do not change `serve.py` or the scoring logic. You can run the pipeline as many times as you like, but leave no other pipelines registered in ZenML when you are done. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
