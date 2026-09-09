#!/usr/bin/env bash
# Reference: a ZenML materializer that saves the picklable parts and rebuilds the SQLite lookup on load,
# plus ArtifactConfig(name="churn_scorer", materializer=...) on the train output.
set -euo pipefail
cd "${APP_DIR:-/app/churn_scoring}"
cat > materializers.py <<'PY'
"""ZenML materializer for ChurnScorer: saves the picklable parts, rebuilds the SQLite lookup on load."""
import json
import os
import pickle
from typing import Any, ClassVar, Tuple, Type

from zenml.enums import ArtifactType
from zenml.materializers.base_materializer import BaseMaterializer

from scorer import ChurnScorer


class ChurnScorerMaterializer(BaseMaterializer):
    ASSOCIATED_TYPES: ClassVar[Tuple[Type[Any], ...]] = (ChurnScorer,)
    ASSOCIATED_ARTIFACT_TYPE: ClassVar[ArtifactType] = ArtifactType.MODEL

    def save(self, data: ChurnScorer) -> None:
        with self.artifact_store.open(os.path.join(self.uri, "model.pkl"), "wb") as f:
            pickle.dump(data.model, f)
        with self.artifact_store.open(os.path.join(self.uri, "meta.json"), "w") as f:
            json.dump({"features": data.features, "threshold": data.threshold}, f)

    def load(self, data_type: Type[Any]) -> ChurnScorer:
        with self.artifact_store.open(os.path.join(self.uri, "model.pkl"), "rb") as f:
            model = pickle.load(f)
        with self.artifact_store.open(os.path.join(self.uri, "meta.json"), "r") as f:
            meta = json.load(f)
        return ChurnScorer(model=model, features=meta["features"], threshold=meta["threshold"])
PY
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("from zenml import pipeline, step", "from zenml import ArtifactConfig, pipeline, step")
s = s.replace("from scorer import ChurnScorer", "from materializers import ChurnScorerMaterializer\nfrom scorer import ChurnScorer")
old = "def train(df: pd.DataFrame) -> ChurnScorer:"; assert old in s
s = s.replace(old, 'def train(df: pd.DataFrame) -> Annotated[ChurnScorer, ArtifactConfig(name="churn_scorer", materializer=ChurnScorerMaterializer)]:')
p.write_text(s)
PY
