"""The training pipeline. `run.py` applies `config.yaml` to it."""
from zenml import pipeline

from steps import evaluate, load_data, split, train


@pipeline
def training_pipeline(test_size: float = 0.3, seed: int = 0, C: float = 1.0) -> None:
    features, labels = load_data()
    x_train, x_test, y_train, y_test = split(features, labels, test_size=test_size, seed=seed)
    model = train(x_train, y_train, C=C)
    evaluate(model, x_test, y_test)
