The retail team's demand forecaster lives in `/app/model_promotion`. `python training.py --algorithm linear|forest` registers a new version of the ZenML model `demand_forecaster` and records its validation error as `val_mae` on that version; `python inference.py [--input data/batch.csv]` runs `batch_forecast`, which loads the forecaster and writes the `predictions` artifact. Two versions have already been trained, and the inference pipeline has been run once. The team noticed that since the second model was trained, inference has quietly got worse.

Put the model registry in order:

1. Promote the version with the **lowest `val_mae`** to the `production` stage. Do not train new versions and do not change the recorded metrics.
2. Change `batch_forecast` so that it loads **whichever version holds the `production` stage at the moment it runs**, instead of the latest version. A later promotion of a different version must be picked up by the very next inference run with no code change, even if that run uses the same input batch as the run before it.
3. Run `python inference.py` once with the fixed pipeline.

Keep the entrypoints, the pipeline names `train_forecaster` and `batch_forecast`, the step names, and the artifact names `batch`, `predictions` and `model`. Leave no other pipelines registered. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
