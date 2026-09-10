# Publishing zenml-bench

Decisions (2026-09-10, Alex): Hub org `zenml`; first push private; v0.1 = all 18 hand-built tasks under `tasks/`, none of `tasks/generated/`. Results uploads stay private until a transcript has been read for anything that should not be public.

Why a frozen version and a growing pool are two different things: a benchmark is a ruler, so a published version never changes (a score from one month must be comparable to the next); the generated instances are fuel for training and can churn. Held-out generated seeds become v0.2 later.

## Three ways people can run the set

1. **From this repo, today, no Hub account.** `registry.json` at the root lists the dataset and its task paths (Harbor's "legacy registry" format: a list of `{name, version, description, tasks:[{name, path}]}`). Anyone can run `harbor run --repo zenml-io/zenml-bench@v0.1 -d zenml-bench@0.1.0 -a <agent> -m <model>`; locally, `harbor run --registry-path registry.json -d zenml-bench ...`. Verified with the `nop` agent on 2026-09-10.
2. **From the Harbor Hub.** `dataset.toml` at the root is the Hub manifest (`harbor init` → dataset, `harbor add --scan tasks`); it pins each task by content digest, so run `harbor sync` after any task change and before publishing. Publishing needs `harbor auth login` (GitHub sign-in) once. **Tasks first, then the dataset**: the manifest references tasks by name and digest and the dataset publish fails with "Task not found (likely not published yet)" until they exist, so `harbor publish tasks/b* tasks/r* -t v0.1 --private` (globs skip `tasks/generated/`), then `harbor publish . -t v0.1 --private` (task ids come from `[task].name` in each `task.toml`, already `zenml/<name>`). Then `harbor run -d zenml/zenml-bench@0.1.0 ...` works for members of the org; re-publish with `--public` to open it.
3. **From the Prime Intellect Environments Hub** (training side). `integrations/prime/zenml_bench/` is a verifiers v1 taskset that points at the Harbor dataset (`repo=zenml-io/zenml-bench@v0.1` + `registry.json` until the Hub id exists; switch `dataset` to `zenml/zenml-bench@0.1.0` and drop `repo`/`registry_path` after step 2). Rewards come from each task's own verifier. Smoke test (loads all 18 tasks from the local registry): see `integrations/prime/README.md`. Publishing needs `prime login` once, then `cd integrations/prime/zenml_bench && prime env push`.

## Release checklist

1. All builders finished and their graders committed (a version whose graders change the next day is worse than a version a day late).
2. `scripts/results_table.py` regenerated; README table and `results/*.md` consistent.
3. Every task passes the four checks on the commit being tagged (`scripts/verify_task.py`, or at least `scripts/grade_local.sh` oracle + noop across `tasks/*`).
4. Bump `[task].version` in every `task.toml` to the release version; `harbor sync` to refresh digests in `dataset.toml`; update `version` in `registry.json` and `dataset.toml`.
5. `git tag v0.1 && git push --tags`.
6. `harbor publish . -t v0.1 --private` (after `harbor auth login`).
7. `prime env push` from `integrations/prime/zenml_bench` (after `prime login`).
8. Results: `harbor upload jobs/<job> --org zenml --private` per baseline job you want on the Hub (private first; transcripts are included), then `harbor hub leaderboard` to curate. Prime's `prime eval push` takes verifiers-format evals, so Hub-side results there come from running the taskset through `vf-eval`, not from Harbor job dirs.

## Status (2026-09-10)

Steps 1–5 done: graders frozen at `v0.1` (28 oracle/noop local checks green: 18 tasks + 10 held-out generated instances), `dataset.toml` digests synced, tag pushed, dataset resolves via `--repo zenml-io/zenml-bench@v0.1`. Step 6 done by Alex on 2026-09-10: 18 tasks and the dataset are on the Hub under `@zenml`, private, revision 1 (https://hub.harborframework.com/datasets/zenml/zenml-bench). Because the Hub entry is private, the Prime wrapper keeps resolving from the public GitHub tag (`--repo zenml-io/zenml-bench@v0.1`) so installing the environment needs no Hub credentials; switch it to the Hub id only after a `--public` re-publish. Steps 7–8 (`prime env push`, `harbor upload`) are Alex's to run: the session's permission classifier blocks auth and publish commands, which is the intended behaviour for outward-facing actions. The Qwen small-model matrix is still running from a snapshot of the same graders; its rows join `results/` and the README table as they land and do not change the published tasks.
