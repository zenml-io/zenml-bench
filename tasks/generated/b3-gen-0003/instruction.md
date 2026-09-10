The project in `/app/modeljob` trains a small model every night from `data/train.csv` using the ZenML pipeline `model_refresh` (entrypoint: `python run.py`, run from `/app/modeljob`).

Yesterday the data file was replaced with new rows at the same path, but the pipeline kept reporting the old evaluation score because ZenML served cached results.

Fix the project so that:

1. when `data/train.csv` changes, the steps that depend on it run again and the reported score reflects the new data;
2. when the file has not changed, an unchanged rerun still reuses cached results for the expensive `fit` step;
3. the entrypoint, the pipeline name `model_refresh`, and the step name `fit` stay the same, and the evaluation score is still logged as the `score` output of the `validate_model` step.

Do not disable caching for the whole pipeline. You can run the pipeline as many times as you like, but leave no other pipelines registered in ZenML when you are done. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
