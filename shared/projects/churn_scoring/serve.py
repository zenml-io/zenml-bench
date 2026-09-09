"""Score new rows with the latest trained scorer. Usage: `python serve.py <rows.csv>` from this directory.

Loads the `churn_scorer` artifact by name from ZenML and prints one JSON list of scores.
"""
import json
import sys

import pandas as pd
from zenml.client import Client

if __name__ == "__main__":
    scorer = Client().get_artifact_version("churn_scorer").load()
    rows = pd.read_csv(sys.argv[1])
    print(json.dumps(scorer.score(rows)))
