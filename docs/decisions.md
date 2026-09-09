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

## 2026-09-09 — which artifact types hash by content (resolves the "open" note above)

`compute_content_hash` is implemented by the built-in materializers (str/int/float/bool/bytes/list/dict…), cloudpickle, dataclass, pydantic, uuid, structured-string. The **pandas integration materializer does not implement it**, so a DataFrame input falls back to its artifact ID in the cache key. Observed consequence: `enable_cache=False` on `load_data` alone makes `train` rerun every time (new DataFrame artifact each run), so it is **not** a valid B3 fix; it is now the `disable_load_cache_only.sh` shortcut. A fitted sklearn model *did* hash by content (`evaluate` stayed cached after `train` reran with identical data), so the model is going through a content-hashing materializer.

## 2026-09-09 — B3 grader design

- Cache-hit assertions are on `train` only (the step the instruction names as expensive), not on `load_data`. Principle: outcome not method; a fix that re-reads a 92 KB CSV every run but reuses training is a working nightly pipeline. In practice this admits no extra solution at this pin (see above), but the grader should not depend on that.
- The grader runs the agent's entrypoint itself (`python run.py`, from `/app/nightly`) five times against its own fixtures a, a, b, b, c and reads the runs it created. Tampering with the store beforehand cannot help, so B3 grades in the same container; no separate verifier box needed.
- Entrypoint is `python run.py`, not `uv run python run.py` as the brief drafted: the image installs into system Python and `uv` would be one more moving part with no benefit.
- Local four-checks result (no Docker): oracle 1, noop 0, `file_dependencies.sh` 1, `cache_func.sh` 1, all four shortcuts 0. Run with `scripts/grade_local.sh tasks/b3-stale-cache [patch.sh]`.
- Docs snapshot in the base image is `llms-full.txt` fetched at build time (latest, not version-pinned). Open: pin it to the 0.96.4 docs.

## 2026-09-09 — Harbor 0.22.0: what the brief got wrong, and what we rely on

Established by installing `harbor==0.22.0` (`uv tool install`) and running a hello task, then B3, with the `oracle` and `nop` agents. Corrections to brief §3.2:

- Local task dirs run with `harbor run -p <dir>`; `-t` is a registry task name. Attempts: `-k`, concurrency: `-n`, output: `-o <dir> --job-name <name>`. Harbor refuses to reuse a job dir whose `lock.json` differs; delete it first.
- The do-nothing agent is called `nop`.
- Reward: the verifier reads `/logs/verifier/reward.json` first and falls back to `reward.txt`. Extra numeric keys in the JSON become metric columns in `result.json`. So research tasks can write `{"reward": 0|1, "gap_closed": x, ...}` exactly as the brief planned.
- `tests/` is uploaded to `/tests` after the agent finishes and `test.sh` runs as the image's default user (root) from the image's `WORKDIR`. `/solution` exists only during oracle runs. In `[verifier] environment_mode = "separate"` Harbor does **not** upload tests; the verifier image must already contain `/tests/test.sh`.
- `[[mcp_servers]]` is `[[environment.mcp_servers]]`. Timeouts are per section (`[agent].timeout_sec`, `[verifier].timeout_sec`). There is no task-level `skills/` convention: skills come from `harbor run --skill <dir|org/repo@ref>` or `[environment].skills_dir` inside the image. The "+ skill" condition is therefore a run-time flag, not a task variant.
- **There is no Harbor LLM proxy.** API keys are passed into the container as env vars. Under `no-network` the agent cannot reach its model. The documented pattern is `[environment] network_mode = "no-network"` plus `[agent] network_mode = "allowlist"` / `allowed_hosts`, or `--allow-agent-host api.anthropic.com` at run time (agent phase only). Agent *installation* happens in the setup phase under the baseline policy, so the image must pre-install the agent or its dependencies.
- **Blocker on this Mac:** Docker Desktop's VM kernel lacks `CONFIG_NFT_FIB_INET`, which Harbor's egress sidecar needs, so `no-network` and `allowlist` are rejected outright. Only `public` runs locally. Options: OrbStack/Colima as the Docker runtime on macOS, or run restricted-network tasks on Linux CI / Modal / Daytona. `task.toml` says `public` until this is decided.
- Base image now pre-installs `nodejs npm procps` (claude-code, codex), `ripgrep` (codex), `tmux` (terminus-2) so agent setup does not need network.
- Harbor builds the task image with `environment/` as the build context, so a task must be self-contained. `scripts/sync_project.sh <project> <task>` copies `shared/projects/<project>` into `environment/<project>`; the copy is committed (Harbor registry pulls task dirs) but `shared/projects/` stays the source of truth.
- Job output: `jobs/<job>/<task>__<id>/{result.json, trial.log, agent/, verifier/}`; the reward is at `result.json` → `verifier_result.rewards.reward`. LLM agents write `agent/trajectory.json` in ATIF format (Harbor RFC 0001); `analyse_trajectories.py` parses that.
- B3 through Harbor: oracle 1.0, nop 0.0 (matches `grade_local.sh`).

## 2026-09-09 — sealed network works under OrbStack; agents baked into the image; baseline models

- OrbStack (installed via Homebrew) provides a Docker runtime whose kernel supports Harbor's egress control. `docker context use orbstack` / `docker context use desktop-linux` switches between the two runtimes; images are per-runtime, so rebuild `zenml-bench/base` after switching. B3 now declares `[environment] network_mode = "no-network"` and `[agent] network_mode = "allowlist"` with the model API hosts. A probe task confirmed `curl https://pypi.org` fails inside the container (exit 35) under this policy.
- Harbor installs agent CLIs during setup, which runs under the sealed baseline policy, but both `claude-code` and `codex` skip the install when the binary is already on PATH. The base image now runs `npm install -g @anthropic-ai/claude-code@latest @openai/codex@latest` (today: Claude Code 2.1.266, codex-cli 0.153.4). This pins agent versions per image build; bump deliberately.
- Harbor requires `-m <model>` for Codex ("Model name is required"). First baseline models: `codex` → `gpt-5.6-terra` (named on OpenAI's Codex models page as the replacement for the retired `gpt-5.4`), `claude-code` → `claude-opus-5`. Both confirmed available to the keys in `.env` via the providers' `/v1/models` endpoints.
- "+ skill" condition: `zenml-io/skills` is laid out as plugins (`skills/<plugin>/skills/<skill>/SKILL.md`), so Harbor's `org/name` shorthand does not find them. `run_baselines.py` clones the repo at pinned commit `e8534cad` into `.skills-cache/` and passes `zenml-pipeline-authoring` and `zenml-quick-wins` via `--skill`.
- Grader rule learned from the first Codex trial (see findings.md): the ZenML store is shared between the agent and the grader, so only assert "step executed" on inputs the agent has never seen.

## 2026-09-09 — B9 modernise-old-api: what 0.96.4 does with 0.4x code

- Gone outright: `zenml.steps.BaseParameters`, `zenml.steps.Output`, `zenml.pipelines.BasePipeline`, `zenml.post_execution`. Still importable: `zenml.steps.step`, `zenml.pipelines.pipeline`, `BaseStep`, `StepContext`. So an old project fails at import, and the grader's "no deprecated symbols" check is automatic: if it runs, they are gone.
- The offline docs include the 0.39.1 → 0.41.0 migration guide, so the task is docs-solvable; expected to saturate like B3. It stays as the regression task for the "unlearn old API" category.
- Trap kept in the task: a step annotated `Tuple[Annotated[...], ...]` that `return`s a function call (not a literal tuple) is treated by ZenML as **one** output (`has_tuple_return` inspects the function's source for a tuple literal). The legacy code returns `train_test_split(...)` directly; a mechanical conversion hits `StepInterfaceError: Unable to unpack step artifact` at run time.
- Grader must defeat the agent's own cache: `load_data()` has no inputs so every rerun is a cache hit. The grader expires every existing step run as a cache candidate with `Client().update_step_run(id, cache_expires_at=now)` (documented API) before each of its runs. Fixture scores with test_size=0.25, C=0.5: a=0.9067, c=0.7467; with defaults (0.3, 1.0): a=0.9056, c=0.75, so dropped parameters are detectable at 1e-4.
- Parameters are checked by value inside the recorded step parameters, flattened, so both plain-argument and pydantic-model parameter styles pass.

## 2026-09-09 — B7 kubernetes-settings: how to grade Kubernetes config with no cluster (tier C1)

- On a local stack ZenML **drops** orchestrator settings that don't belong to the active orchestrator's flavor at compile time (warning "Not including stack component settings with key …"), whether keyed `orchestrator` or `orchestrator.kubernetes`. They never reach the run record. Resource settings *are* recorded (with a warning that the local orchestrator ignores them). So the run record cannot be the grader.
- Registering a Kubernetes orchestrator against the local SQLite store works (warning only: "component running remotely while connected to the local database"). The task image registers `k8s` (flavor kubernetes), `reg` (default container registry) and `k8s-stack`; the active stack stays `default`.
- Grader = dry-run compile: import `pipeline.training_pipeline`, apply `config.yaml` the way `run.py` does (`pipe._parse_config_file(...)` → `PipelineRunConfiguration`, plus `with_options(config_path=...)`), `pipe.prepare()`, then `Compiler().compile(pipeline, stack=Stack.from_model(Client().get_stack("k8s-stack")), run_configuration)`. In the compiled deployment the settings key is renamed to `orchestrator:<component-name>` (`orchestrator:k8s`), stored as a generic `BaseSettings`; re-validate with `KubernetesOrchestratorSettings.model_validate(raw.model_dump())`.
- Pipeline-level `pod_settings` are merged into every step at compile, so "only `train` gets the GPU" is checked by asserting the other steps have none.
- `ResourceSettings.memory` rejects Kubernetes quantities like `8Gi` (`SettingsResolvingError`) and wants `8GB`; `KubernetesPodSettings.resources` takes `8Gi`. Both forms are accepted by the grader (the orchestrator honours both). Kept as a realistic trap; the instruction says "8Gi".
- Base image now installs the `kubernetes` client (needed by the settings classes).

## 2026-09-09 — solution scripts under `verify_task.py`

A shortcut or alternative that builds on the reference must not call `../../solution/solve.sh`: inside Harbor the script *is* `/solution/solve.sh` and it recurses until the container is killed (observed: "shell level (1000) too high"). `verify_task.py` now copies the real reference to `solution/reference.sh` in the temp task, and scripts use `REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"`. Crashed trials show as `nan` rewards (FAIL) rather than crashing the verifier.
