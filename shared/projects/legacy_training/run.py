"""Entrypoint. Run from this directory: `python run.py`. Prints the evaluation score of the run it just made."""
from zenml.pipelines import pipeline
from zenml.post_execution import get_pipeline

from steps import SplitParams, TrainParams, evaluate, load_data, split, train


@pipeline
def training_pipeline(load_data, split, train, evaluate):
    features, labels = load_data()
    x_train, x_test, y_train, y_test = split(features, labels)
    model = train(x_train, y_train)
    evaluate(model, x_test, y_test)


if __name__ == "__main__":
    training_pipeline(
        load_data=load_data(),
        split=split(params=SplitParams(test_size=0.25, seed=0)),
        train=train(params=TrainParams(C=0.5)),
        evaluate=evaluate(),
    ).run()
    latest = get_pipeline("training_pipeline").runs[-1]
    print("score:", latest.get_step("evaluate").output.read())
