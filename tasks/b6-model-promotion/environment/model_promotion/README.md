# model_promotion

Demand forecasting for the retail team. `python training.py --algorithm linear|forest` trains a model and registers it as a new version of the ZenML model `demand_forecaster`, with `val_mae` recorded on the version. `python inference.py [--input data/batch.csv]` runs `batch_forecast`, which loads the forecaster from the model registry and produces the `predictions` artifact. `make_data.py` regenerates the data.
