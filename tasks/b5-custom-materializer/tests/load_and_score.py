"""Fresh-process loader: load `churn_scorer` by name from ZenML, score a CSV, print JSON. Run with cwd = the project."""
import json
import sys

import pandas as pd
from zenml.client import Client

scorer = Client().get_artifact_version("churn_scorer").load()
print(json.dumps({"scores": scorer.score(pd.read_csv(sys.argv[1])), "type": type(scorer).__module__ + "." + type(scorer).__qualname__}))
