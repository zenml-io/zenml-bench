The project in `/app/training_job` trains a small model every night from `data/training_set.csv` using the ZenML pipeline `train_nightly` (entrypoint: `python run.py`, run from `/app/training_job`).

Yesterday the data file was replaced with new rows at the same path, but the pipeline kept reporting the old evaluation val_accuracy because ZenML served cached results.

Fix the project so that:

1. when `data/training_set.csv` changes, the steps that depend on it run again and the reported val_accuracy reflects the new data;
2. when the file has not changed, an unchanged rerun still reuses cached results for the expensive `train` step;
3. the entrypoint, the pipeline name `train_nightly`, and the step name `train` stay the same, and the evaluation val_accuracy is still logged as the `val_accuracy` output of the `assess` step.

Do not disable caching for the whole pipeline. You can run the pipeline as many times as you like, but leave no other pipelines registered in ZenML when you are done. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
