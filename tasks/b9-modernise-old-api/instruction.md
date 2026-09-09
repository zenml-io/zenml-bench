The project in `/app/legacy_training` was written against an old ZenML release and no longer runs on the ZenML version installed here (`python -c "import zenml; print(zenml.__version__)"`). The entrypoint is `python run.py`, run from `/app/legacy_training`.

Update the project so it runs on the installed ZenML with the same behaviour:

1. `python run.py` completes and prints a line `score: <value>` with the evaluation score of the run it just made.
2. The pipeline is still called `training_pipeline` and still has the four steps `load_data`, `split`, `train`, `evaluate`, with the same step outputs and output names as before (`features`/`labels`, `x_train`/`x_test`/`y_train`/`y_test`, the trained model, `score`). Downstream tooling reads artifacts by those names.
3. The run uses the same parameter values as before (`test_size=0.25`, `seed=0`, `C=0.5`) and they are recorded on the run so they can be audited later.
4. The model, the split, and the score are computed the same way, so the score on the current data is unchanged.

Keep using ZenML for the pipeline (do not replace it with a plain script). You can run the pipeline as many times as you like, but leave no other pipelines registered in ZenML when you are done (running a step on its own registers a pipeline named after the step). ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
