The risk team's credit-default training lives in `/app/credit_script/train.py`: `python train.py [--data data/credit.csv]` prepares the data, trains a classifier, evaluates it and prints `accuracy=…`. Nothing is tracked: no model is stored, no metric is recorded, and nobody can tell which data a printed number came from.

Turn the script into a ZenML pipeline named `credit_training` so that every run is recorded:

1. Separate `@step`s for preparing the data, training and evaluating (at least three steps; a loading step on its own is fine too), with typed inputs and outputs, wired in the order the script uses them so that the model the evaluation step scores is the one the training step produced.
2. The trained model is a step output artifact named `model`, and the test accuracy is a step output artifact named `accuracy` (a float).
3. The results are preserved: on `data/credit.csv`, and on any other file passed with `--data`, the recorded `accuracy` equals what the original script prints for that file (same feature engineering, split, and model settings).
4. `python train.py [--data <path>]` stays the entrypoint and runs the pipeline.

Leave no other pipelines registered when you are done. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
