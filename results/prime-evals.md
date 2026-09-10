# Prime evals: zenml-bench through verifiers v1 (2026-09-10)

What ran: the pushed environment `zenml/zenml-bench` (wrapper 0.1.1, `integrations/prime/zenml_bench`) through verifiers 0.3.1's v1 runner (`eval`, not the legacy `vf-eval`), Codex harness (Codex 0.147.0 installed by the harness inside the box), `gpt-5.4-mini` at the OpenAI endpoint, local docker runtime (OrbStack) with one prebuilt image per task (`scripts/build_task_images.sh`), task-authored timeouts kept, 18 tasks × 1 rollout, 4 in flight. Config: `results/prime-evals/full-codex-gpt-5.4-mini/configs/eval.toml`; converted results for `prime eval push` in the same directory. Raw `traces.jsonl` (9.8 MB, transcripts as a trace graph) stays out of git.

## Result: 17/18

| task | vf-eval (codex, gpt-5.4-mini) | model calls | agent s | grade s | Harbor rows, same harness + model | Harbor rows, codex gpt-5.6-terra |
|---|---|---|---|---|---|---|
| b1-source-root-repair | 1 | 19 | 86 | 13 | – | 3/3 |
| b10-why-did-it-fail | 1 | 13 | 58 | 8 | 3/3 | 3/3 |
| b10h-why-did-it-fail-hard | 1 | 20 | 110 | 24 | 3/3 | 3/3 |
| b11-stack-registration | 1 | 26 | 178 | 6 | – | 3/3 |
| b14-artifact-retrieval | 1 | 45 | 210 | 5 | – | 3/3 |
| b14h-artifact-retrieval-hard | 1 | 32 | 158 | 5 | 3/3 | 3/3 |
| b2-script-to-pipeline | 1 | 21 | 119 | 12 | – | 3/3 |
| b3-stale-cache | 1 | 39 | 149 | 25 | 3/3 | 3/3 |
| b4-nondeterministic-step | 1 | 37 | 163 | 7 | – | 3/3 |
| b5-custom-materializer | 1 | 16 | 63 | 6 | 3/3 | 3/3 |
| b6-model-promotion | **0** | 19 | 76 | 9 | – | 3/3 |
| b7-kubernetes-settings | 1 | 52 | 241 | 8 | 2/3 | 3/3 |
| b9-modernise-old-api | 1 | 44 | 172 | 17 | 3/3 | 3/3 |
| r1-bare-clock-improve-within-budget | 1 | 25 | 153 | 1 | – | 5/5 |
| r1-bare-improve-within-budget | 1 | 34 | 215 | 1 | – | 3/3 |
| r1-clock-improve-within-budget | 1 | 45 | 283 | 3 | – | 5/5 |
| r1-improve-within-budget | 1 | 64 | 430 | 3 | 3/3 | 3/3 |
| r2-screen-then-confirm | 1 | 33 | 227 | 4 | – | 3/3 |

Harbor rows are the bare condition from `results/*.jsonl` (Harbor 0.22.0, Codex as installed in the base image). "–" means no Harbor run of gpt-5.4-mini on that task yet; the only Harbor sample of `gpt-5.4-mini` on eight tasks is 23/24.

Wall clock 17 min for the whole set (4 concurrent); 3,462 s summed per-rollout time. Tokens as recorded by verifiers' interception server: 768,948 prompt, 233,433 completion over 559 model calls (no cache hits recorded; Codex through the interception path reports `cached_input_tokens: 0`). Cost not measured by verifiers (no pricing table); by analogy with the Harbor gpt-5.4-mini rows (US$0.10–0.39 per trial) the run cost roughly US$3–5.

## Extra verifier metrics survive

Every task's extra `reward.json` keys landed in the trace's `metrics` (e.g. b10 `agent_runs`, b11 `global_active_too`, b5 `used_custom_materializer`, r-series `gap_closed`, `hidden_log_loss`, `experiments`), so a trainer or the hub viewer sees the same per-trial detail Harbor records.

## Discrepancies and their causes

- **b6-model-promotion 0 here vs 3/3 for codex gpt-5.6-terra under Harbor.** No Harbor sample of gpt-5.4-mini on b6 exists, so this is a model difference until a Harbor run says otherwise (the Qwen 9B rows are 0/5, the task is not saturated for small models). Not a runtime artefact: the agent completed normally (19 calls, `agent_completed`) and the grader ran (9 s).
- **Reward key differs by task.** Tasks that write `reward.txt` (b3, b7, b9) score under the name of verifiers' reward function, `solved`; tasks that write `reward.json` with a `reward` key score under `reward`. Both have weight 1 and count fully in `trace.reward`; a reader that looks only at `rewards.reward` (the first version of the converter did) undercounts by three. Fixed in `scripts/harbor_to_prime_eval.py`.
- **Working directory.** verifiers starts the container with `--workdir /app` (its own default) while Harbor uses the image's `WORKDIR` (`/app/<project>`); the instructions name the project path and every `test.sh` uses `APP_DIR`, so grading was unaffected, but Codex spends its first call on `ls`/`cd`.
- **Transient OpenAI TLS errors** (`SSLV3_ALERT_BAD_RECORD_MAC`, 8 over the run) were retried by the interception server and did not fail a rollout.
- **Timeouts kept.** `ignore_timeouts=false` in the wrapper, so `[agent].timeout_sec` (1500–2400 s) applied; no rollout came close (max 430 s agent time).
- **Harness version.** verifiers installed Codex 0.147.0 (its pin) in the box; Harbor's rows used the Codex baked in the base image (0.153.4 in the September jobs). Same model, slightly different agent.

## Converted Harbor jobs (route 2)

`results/prime-evals/harbor-b10-codex-terra-bare/` (codex, gpt-5.6-terra, 3 trials, 3/3, no transcripts) and `results/prime-evals/harbor-b10-terminus2-qwen3.5-9b-bare/` (terminus-2, qwen3.5-9b, 5 trials, 3/5, with transcripts, 540 KB, scanned for key-shaped strings). Their metadata `note` says "run through Harbor 0.22.0 with the <harness> harness, converted ...; not a vf-eval run".

## Push commands (Alex)

```
prime eval push results/prime-evals/full-codex-gpt-5.4-mini --env zenml/zenml-bench --name "verifiers v1 codex gpt-5.4-mini 18x1 docker 2026-09-10"
prime eval push results/prime-evals/harbor-b10-codex-terra-bare --env zenml/zenml-bench --name "Harbor 0.22 codex gpt-5.6-terra b10 x3 (converted)"
prime eval push results/prime-evals/harbor-b10-terminus2-qwen3.5-9b-bare --env zenml/zenml-bench --name "Harbor 0.22 terminus-2 qwen3.5-9b b10 x5 (converted)"
```
