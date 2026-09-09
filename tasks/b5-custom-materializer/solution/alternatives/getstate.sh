#!/usr/bin/env bash
# Alternative: no materializer. __getstate__/__setstate__ drop and rebuild the connection, so ZenML's
# cloudpickle fallback works; the output is named with ArtifactConfig. Valid by outcome; recorded as a metric.
set -euo pipefail
cd "${APP_DIR:-/app/churn_scoring}"
python - <<'PY'
from pathlib import Path
p = Path("scorer.py"); s = p.read_text()
old = "    def boost_for(self, segment: int) -> float:"; assert old in s
s = s.replace(old, '''    def _build_lookup(self) -> None:
        self.lookup = sqlite3.connect(":memory:")
        self.lookup.execute("CREATE TABLE segment_boost (segment INTEGER PRIMARY KEY, boost REAL)")
        self.lookup.executemany("INSERT INTO segment_boost VALUES (?, ?)", SEGMENT_BOOST.items())

    def __getstate__(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "lookup"}

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        self._build_lookup()

''' + old)
p.write_text(s)
p = Path("run.py"); s = p.read_text()
s = s.replace("from zenml import pipeline, step", "from zenml import ArtifactConfig, pipeline, step")
old = "def train(df: pd.DataFrame) -> ChurnScorer:"; assert old in s
s = s.replace(old, 'def train(df: pd.DataFrame) -> Annotated[ChurnScorer, ArtifactConfig(name="churn_scorer")]:')
p.write_text(s)
PY
