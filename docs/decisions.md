# Decisions and resolved "(verify)" items

One entry per decision, dated, newest at the bottom. When a "(verify)" item from the brief is checked, record what was actually found, including the command or code that showed it.

## 2026-09-09 — pins

- ZenML `0.96.4` (latest on PyPI today). Its classifiers list Python 3.10–3.14; we use **Python 3.14**.
- Harbor `0.22.0` (latest on PyPI today). Not yet installed or exercised.
- Local dev install must be `zenml[local]`, not bare `zenml`. Since some release before 0.96 the SQLite store's dependencies (`sqlmodel` and friends) moved into the `local` extra; bare `zenml` raises `ImportError` on first client use unless connected to a server. The base image must install `zenml[local]==<pin>`.

## 2026-09-09 — env var for an isolated config

`ZENML_CONFIG_PATH` is the variable (confirmed in `zenml/constants.py`: `ENV_ZENML_CONFIG_PATH = "ZENML_CONFIG_PATH"`). Pointing it at a fresh directory gives a fresh SQLite store, fresh default stack, and no contact with the user's real config. `ZENML_ANALYTICS_OPT_IN=false` also confirmed as the analytics switch.

## 2026-09-09 — B3 stale-cache: the fault and three verified fixes (Level 0 spike)

Spike run locally on the `shared/projects/nightly` project, sequence of datasets **a, a, b, b, c** copied to `data/train.csv` between runs, each fix in its own fresh store. Statuses read back with `Client().list_pipeline_runs(pipeline="nightly_training")` and `run.steps[name].status`.

**Unfixed project** (`load_data(path: str)`): run 1 completed, runs 2–5 all `cached`, score stuck at dataset a's value (0.9111) even after b and c were copied in. Fault reproduced.

**All three fixes below produced the target pattern**: run 1 completed → run 2 cached → run 3 completed → run 4 cached → run 5 completed, with scores 0.9111 / 0.9111 / 0.7611 / 0.7611 / 0.7778, and `train` cached exactly when `load_data` was cached.

1. **Brief's reference**: uncached `content_hash(path) -> str` step whose output is passed into `load_data(path, digest)`. Works with the *default* cache policy on `load_data`.
2. `@step(cache_policy=CachePolicy(file_dependencies=["data/train.csv"]))` on `load_data`. Path is relative to the source root (the `zenml init` directory).
3. `@step(cache_policy=CachePolicy(cache_func=data_digest))` where `data_digest()` returns the file's sha256.

**Why fix 1 works despite the digest being a new artifact version every run** (this was the risk the brief flagged): ZenML's cache key uses an input artifact's *content hash* when the materializer can compute one, and only falls back to the artifact *ID* when it cannot. Observed: run 1 and run 2 produced digest artifacts with different IDs (`de213353` v1, `59f79a77` v2) but identical `content_hash`, and `load_data` got the identical `cache_key` (`9361e38dbb`) in both runs. The docs' phrase "artifact values or IDs" means values first, IDs as fallback. Built-in materializers (str, pandas DataFrame) support content hashing.

Consequences for the task: the grader's expected statuses are exactly the pattern above; `solution/solve.sh` can be fix 1 and `solution/alternatives/` gets fixes 2 and 3; `disable_train_cache.sh` and `disable_all_caching.sh` shortcuts will fail the "run 2 / run 4 cached" checks; `hardcode_score.sh` will fail the dataset-c check. Fixture scores at this pin: a=0.9111, b=0.7611, c=0.7778 (accuracy, `LogisticRegression(max_iter=1000)`, 30% test split, `random_state=0`).

Open: whether `train` being cached in run 2 relies on the pandas materializer's content hash or on the same artifact ID (the `load_data` output *was* the same artifact in run 2 because `load_data` was cached, so both would give the same answer here). Not load-bearing for B3 but worth knowing for B4 (nondeterministic step).
