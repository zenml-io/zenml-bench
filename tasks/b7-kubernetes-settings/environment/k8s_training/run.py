"""Entrypoint. Run from this directory: `python run.py`. Configuration lives in `config.yaml`."""
from pipeline import training_pipeline

if __name__ == "__main__":
    training_pipeline.with_options(config_path="config.yaml")()
