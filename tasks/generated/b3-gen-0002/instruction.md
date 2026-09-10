The project in `/app/overnight` trains a small model every night from `data/latest.csv` using the ZenML pipeline `nightly_training` (entrypoint: `python run.py`, run from `/app/overnight`).

Yesterday the data file was replaced with new rows at the same path, but the pipeline kept reporting the old evaluation accuracy because ZenML served cached results.

Fix the project so that:

1. when `data/latest.csv` changes, the steps that depend on it run again and the reported accuracy reflects the new data;
2. when the file has not changed, an unchanged rerun still reuses cached results for the expensive `assess` step;
3. the entrypoint, the pipeline name `nightly_training`, and the step name `assess` stay the same, and the evaluation accuracy is still logged as the `accuracy` output of the `assess` step.

Do not disable caching for the whole pipeline. You can run the pipeline as many times as you like, but leave no other pipelines registered in ZenML when you are done. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
