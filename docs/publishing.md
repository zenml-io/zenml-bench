# Publishing zenml-bench

Decisions (2026-09-10, Alex): Hub org `zenml`; first push private; v0.1 = all 18 hand-built tasks under `tasks/`, none of `tasks/generated/`. Results uploads stay private until a transcript has been read for anything that should not be public.

Why a frozen version and a growing pool are two different things: a benchmark is a ruler, so a published version never changes (a score from one month must be comparable to the next); the generated instances are fuel for training and can churn. Held-out generated seeds become v0.2 later.

## Three ways people can run the set

1. **From this repo, today, no Hub account.** `registry.json` at the root lists the dataset and its task paths (Harbor's "legacy registry" format: a list of `{name, version, description, tasks:[{name, path}]}`). Anyone can run `harbor run --repo zenml-io/zenml-bench@v0.1 -d zenml-bench@0.1.0 -a <agent> -m <model>`; locally, `harbor run --registry-path registry.json -d zenml-bench ...`. Verified with the `nop` agent on 2026-09-10.
2. **From the Harbor Hub.** `dataset.toml` at the root is the Hub manifest (`harbor init` → dataset, `harbor add --scan tasks`); it pins each task by content digest, so run `harbor sync` after any task change and before publishing. Publishing needs `harbor auth login` (GitHub sign-in) once. **Tasks first, then the dataset**: the manifest references tasks by name and digest and the dataset publish fails with "Task not found (likely not published yet)" until they exist, so `harbor publish tasks/b* tasks/r* -t v0.1 --private` (globs skip `tasks/generated/`), then `harbor publish . -t v0.1 --private` (task ids come from `[task].name` in each `task.toml`, already `zenml/<name>`). Then `harbor run -d zenml/zenml-bench@0.1.0 ...` works for members of the org; re-publish with `--public` to open it.
3. **From the Prime Intellect Environments Hub** (training side). `integrations/prime/zenml_bench/` is a verifiers v1 taskset that points at the Harbor dataset (`repo=zenml-io/zenml-bench@v0.1` + `registry.json` until the Hub id exists; switch `dataset` to `zenml/zenml-bench@0.1.0` and drop `repo`/`registry_path` after step 2). Rewards come from each task's own verifier. Smoke test (loads all 18 tasks from the local registry): see `integrations/prime/README.md`. Publishing needs `prime login` once, then `cd integrations/prime/zenml_bench && prime env push`.

## Going public

Order: (1) make the GitHub repo public (the Prime environment and the `--repo` route point at it, and the base image is only buildable from it); (2) Harbor Hub: `harbor publish --public` only sets visibility for *new* packages, existing ones keep theirs, so flip the 18 tasks and the dataset in the Hub UI (or bump the version and re-publish with `--public`); (3) Prime: `prime env push --visibility PUBLIC` on the next push, or the Hub UI; (4) uploaded jobs: `harbor upload <job> --public` on a re-upload updates visibility. Before each step run `scripts/check_public.sh [jobs/<job> ...]`. Known trade-off of public tasks: solutions and tests are part of the package (Harbor's norm, as with Terminal-Bench), so future models may have seen them; held-out generated instances are the answer to that.

## Release checklist

1. All builders finished and their graders committed (a version whose graders change the next day is worse than a version a day late).
2. `scripts/results_table.py` regenerated; README table and `results/*.md` consistent.
3. Every task passes the four checks on the commit being tagged (`scripts/verify_task.py`, or at least `scripts/grade_local.sh` oracle + noop across `tasks/*`).
4. Bump `[task].version` in every `task.toml` to the release version; `harbor sync` to refresh digests in `dataset.toml`; update `version` in `registry.json` and `dataset.toml`.
5. `git tag v0.1 && git push --tags`.
6. `harbor publish . -t v0.1 --private` (after `harbor auth login`).
7. `prime env push` from `integrations/prime/zenml_bench` (after `prime login`).
8. Results: `harbor upload jobs/<job> --org zenml --private` per baseline job you want on the Hub (private first; transcripts are included), then `harbor hub leaderboard` to curate. Prime's `prime eval push` takes verifiers' legacy eval layout (`metadata.json` + `results.jsonl`); see "Prime evals" below for the two routes (a real verifiers v1 run, or Harbor jobs converted by `scripts/harbor_to_prime_eval.py`).

## Status (2026-09-10)

Steps 1–5 done: graders frozen at `v0.1` (28 oracle/noop local checks green: 18 tasks + 10 held-out generated instances), `dataset.toml` digests synced, tag pushed, dataset resolves via `--repo zenml-io/zenml-bench@v0.1`. Step 6 done by Alex on 2026-09-10: 18 tasks and the dataset are on the Hub under `@zenml`, private, revision 1 (https://hub.harborframework.com/datasets/zenml/zenml-bench). Because the Hub entry is private, the Prime wrapper keeps resolving from the public GitHub tag (`--repo zenml-io/zenml-bench@v0.1`) so installing the environment needs no Hub credentials; switch it to the Hub id only after a `--public` re-publish. Step 7 done by Alex on 2026-09-10: `prime env push` created `zenml/zenml-bench` on the Environments Hub (https://app.primeintellect.ai/dashboard/environments/zenml/zenml-bench; `prime env install zenml/zenml-bench`), published as verifiers v1. The push writes `integrations/prime/zenml_bench/.prime/` (gitignored). Step 8 started: `harbor upload jobs/baseline-b10-why-did-it-fail-codex-bare --org zenml --private` uploaded 3 trials linked to the Hub task (https://hub.harborframework.com/jobs/c7000f82-1a11-4772-afb0-5e8c462947f5). Uploads include full transcripts; read one before uploading more or going public. Remaining jobs upload the same way, then `harbor hub leaderboard` to curate: the session's permission classifier blocks auth and publish commands, which is the intended behaviour for outward-facing actions. The Qwen small-model matrix is still running from a snapshot of the same graders; its rows join `results/` and the README table as they land and do not change the published tasks.

## Prime evals (2026-09-10)

Two kinds of result can sit under `zenml/zenml-bench` on the Prime Evals hub; both are private by default and Alex runs the push commands.

**Route 1: a real verifiers v1 run.** The taskset (wrapper 0.1.1) runs through verifiers' own runner, the Codex harness and the local docker runtime; mechanism notes in `docs/decisions.md` ("Prime evals"). Setup once: `docker context use orbstack`, base image built, `scripts/build_task_images.sh` (one `zenml-bench/<task>:0.1.0` image per task, because verifiers never builds Dockerfiles), a venv with `verifiers[harbor]==0.3.1` on Python 3.12 and the wrapper installed into it (`uv pip install -e integrations/prime/zenml_bench`). Then, with `set -a; source .env; set +a`:

```
eval @ results/prime-evals/full-codex-gpt-5.4-mini/configs/eval.toml --no-rich -o outputs --run.name <name>   # the TOML: model, [client] base_url/api_key_var, [env.taskset] id, [env.agent.harness] id = "codex", [env.agent.runtime] type = "docker"
```

Outputs land in `outputs/<name>/traces.jsonl` (+ `configs/resolved/eval.json`, re-runnable with `--resume`). The run's own upload is `--push` (default on, needs `prime login`; we ran `--no-push`); to upload a finished run later, convert it with `scripts/harbor_to_prime_eval.py --from-traces outputs/<name>` and push the result: `prime eval push results/prime-evals/full-codex-gpt-5.4-mini --env zenml/zenml-bench --name "vf-eval codex gpt-5.4-mini 18x1 (docker, 2026-09-10)"`. Result on 2026-09-10: 17/18 (b6 0), 17 min wall clock, ~US$3–5; numbers and the comparison with the Harbor rows in `results/prime-evals.md`.

**Route 2: existing Harbor baselines, converted.** `scripts/harbor_to_prime_eval.py jobs/<job>... --out results/prime-evals/<name>/ [--transcripts]` writes the `metadata.json` + `results.jsonl` layout `prime eval push` reads (one row per trial: reward, verifier metrics, tokens, cost, phase timings; transcripts only with `--transcripts`, from `agent/trajectory.json`). The metadata `note` states the rows were run through Harbor 0.22.0 with the named harness and converted, so nothing is presented as a vf-eval run. All jobs in one conversion must share one harness and one model. Demonstrations committed: `results/prime-evals/harbor-b10-codex-terra-bare/` (no transcripts) and `results/prime-evals/harbor-b10-terminus2-qwen3.5-9b-bare/` (with transcripts; scanned for key-shaped strings, none). Push:

```
prime eval push results/prime-evals/harbor-b10-codex-terra-bare --env zenml/zenml-bench --name "Harbor 0.22 codex gpt-5.6-terra b10 x3 (converted)"
prime eval push results/prime-evals/harbor-b10-terminus2-qwen3.5-9b-bare --env zenml/zenml-bench --name "Harbor 0.22 terminus-2 qwen3.5-9b b10 x5 (converted)"
```

Wrapper re-push after the 0.1.1 fix (no `__all__` in 0.1.0, so the pushed environment could not be loaded; Dockerfile-only tasks now map to prebuilt images): `cd integrations/prime/zenml_bench && prime env push`.
