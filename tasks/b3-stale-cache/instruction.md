The project in `/app/nightly` trains a small model every night from `data/train.csv` using the ZenML pipeline `nightly_training` (entrypoint: `python run.py`, run from `/app/nightly`).

Yesterday the data file was replaced with new rows at the same path, but the pipeline kept reporting the old evaluation score because ZenML served cached results.

Fix the project so that:

1. when `data/train.csv` changes, the steps that depend on it run again and the reported score reflects the new data;
2. when the file has not changed, an unchanged rerun still reuses cached results for the expensive `train` step;
3. the entrypoint, the pipeline name `nightly_training`, and the step name `train` stay the same, and the evaluation score is still logged as the `score` output of the `evaluate` step.

Do not disable caching for the whole pipeline. You can run the pipeline as many times as you like. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
