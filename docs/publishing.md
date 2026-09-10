# Publishing zenml-bench

Decisions (2026-09-10, Alex): Hub org `zenml`; first push private; v0.1 = all 18 hand-built tasks under `tasks/`, none of `tasks/generated/`. Results uploads stay private until a transcript has been read for anything that should not be public.

Why a frozen version and a growing pool are two different things: a benchmark is a ruler, so a published version never changes (a score from one month must be comparable to the next); the generated instances are fuel for training and can churn. Held-out generated seeds become v0.2 later.

## Three ways people can run the set

1. **From this repo, today, no Hub account.** `registry.json` at the root lists the dataset and its task paths (Harbor's "legacy registry" format: a list of `{name, version, description, tasks:[{name, path}]}`). Anyone can run `harbor run --repo zenml-io/zenml-bench@v0.1 -d zenml-bench@0.1.0 -a <agent> -m <model>`; locally, `harbor run --registry-path registry.json -d zenml-bench ...`. Verified with the `nop` agent on 2026-09-10.
2. **From the Harbor Hub.** `dataset.toml` at the root is the Hub manifest (`harbor init` → dataset, `harbor add --scan tasks`); it pins each task by content digest, so run `harbor sync` after any task change and before publishing. Publishing needs `harbor auth login` (GitHub sign-in) once, then `harbor publish . -t v0.1 --private` publishes the dataset and the 18 tasks it references (task ids come from `[task].name` in each `task.toml`, already `zenml/<name>`). Then `harbor run -d zenml/zenml-bench@0.1.0 ...` works for members of the org; re-publish with `--public` to open it.
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

## Not done yet (2026-09-10)

Steps 5–8 wait for the hardening agent's final commit and for Alex's two interactive logins (`! harbor auth login`, `! prime login` in the session). Version bump and `harbor sync` are part of the freeze, not before it.
