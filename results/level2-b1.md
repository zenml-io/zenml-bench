# Baseline — task B1 `source-root-repair`

Date: 2026-09-10. Frontier tier only, bare condition, 3 attempts per cell (Harbor 0.22.0, sealed network with the model API allowlisted, `-n 2`). Raw rows: `b1-source-root-repair-baseline-l2.jsonl` (the Codex rows are from the re-run after the grader fix described below; the first Codex run is kept under `jobs/…-codex-bare-l2-v1`, not committed).

| harness | model | condition | pass rate | removed stray `.zen` + init at root | `sys.path` fix in `daily.py` | added `__init__.py` files | checked sources with `source_utils` | read docs | median tokens | mean cost | mean minutes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 751k | $0.83 | 3.2 |
| codex | gpt-5.6-terra | bare | 3/3 (first run: 0/3, grader bug) | 3/3 | 3/3 | 0/3 | 0/3 | 3/3 | 418k | $0.24 | 1.7 |

## What they did

All six diagnosed the cause in the same words the decision log uses: the `.zen` directory in `jobs/backfill` made that directory ZenML's source root, so step sources were recorded relative to it (`run.load_history`) and are not importable from `/app/analytics`. All six removed the stray repository, created one at `/app/analytics`, and added a `sys.path.insert` to `pipelines/daily.py` (nobody expected `zenml init` to fix the Python import, which it does not). Claude Code additionally added `__init__.py` files to `pipelines/`, `jobs/` and `jobs/backfill/`, read the ZenML source-resolution code, and proved the recorded sources with `zenml.utils.source_utils.load(...)` from the project root, which is exactly what the grader does. Codex ran both entrypoints and read `step.spec.source` back through the client.

**The first Codex run scored 0/3 because of a grader bug, not a wrong fix.** All three trials also ran `zenml project register analytics --set` to isolate the analytics pipelines from the neighbour's in their own ZenML *project*. My grader's client listed runs and pipelines in its own active project only, which after `--set` was `analytics`, so the neighbour's `legacy_report` run in project `default` was invisible ("expected exactly one new run, found 0"). The grader now unions runs and pipelines over `Client().list_projects()`, `separate_project.sh` reproduces the approach as an alternative, and the Codex cell was re-run (3/3; the re-run trials did not use a separate project).

## Findings

1. **Saturated (6/6)** once the grader accepted the project-isolation route. The fault's mechanism (repository = source root, found from the CWD upward) is described in the offline docs' "set up your repository" section, which every trial read.
2. **ZenML projects are a valid isolation tool that agents reach for unprompted**, and a grader that reads "the store" through a single client sees only one project. Rule added to `docs/task-authoring.md`: list runs, pipelines and artifacts across projects (or bind the client to each entrypoint's repository) whenever an agent could legitimately create a project.
3. **Nobody was confused by the neighbour**: every trial checked `legacy_reports` before and after (Claude Code hashed its files). The collateral check did its job silently.
