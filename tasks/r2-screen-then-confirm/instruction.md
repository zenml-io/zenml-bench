`/app/research` is a small research project: a binary classifier scored by validation log loss (lower is better), run as the ZenML pipeline `research` (entrypoint `python research.py --config <yaml> [--seed N]`, run from `/app/research`; see the project README). The current config, `configs/baseline.yaml`, is weak. Find a better one, confirm it on several seeds, and promote it.

Rules of the loop:

1. **Budget: at most 12 runs of the `research` pipeline in total**, whatever their status. The grader counts every run the ZenML store shows for that pipeline, including your screening runs. A 13th run fails the task.
2. `prepare.py` is read-only. It defines the data, the metric, the screening seeds and `subsample(X, y, seed)`. Your `train` step must take its training rows from `prepare.subsample` with the run's seed; do not train on the full training set. The grader evaluates with its own copy of the evaluation code on data you cannot see, so changing `prepare.py` cannot help.
3. Everything else in `research.py` and `configs/` is yours to change: model family, hyperparameters, feature engineering inside `train`, new config files.
4. When you are done, **promote your best model version to the `production` stage** of the ZenML model `research_model` (the README shows the CLI and client calls). The promotion counts only with evidence: the production version must be linked to **at least three completed runs of `research` on three distinct seeds**, each of whose `train` step produced a `model` artifact of that version, and **the mean of those runs' recorded `val_log_loss` must be at most 0.56** (the baseline scores about 0.66). A version promoted on one seed scores zero even if its model is good. The grader loads the most recent run-produced `model` artifact of the production version and scores it on the hidden data.
5. Keep the pipeline name `research` and leave no other pipelines registered in ZenML.

Pass condition: the evidence rule above holds and the promoted model closes at least half of the gap between the baseline config and a strong reference config on the hidden data. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
