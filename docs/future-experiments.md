# Future experiments

Ideas that are not part of the published benchmark. Each entry says what question it answers, what it would measure, and what it costs, so a later session can pick one up without re-deriving it. Code for an experiment lives under `experiments/<name>/`; its job dirs and raw outputs are gitignored, the arm definitions and analysis scripts are tracked so results are reproducible. Results of these experiments are not uploaded to the Hubs and do not enter `results/` or the README table unless a decision says so.

## 1. Framework comparison: does the bookkeeping tool change how an autonomous researcher behaves? (Hamza, 2026-09-10)

**Question.** The wall-clock comparison (`results/level3-comparison.md`) showed Codex reaching a clearly better model with ZenML than with plain scripts (5/5 non-overlapping hidden log loss), apparently because it treated a pipeline run as a record of a decision made elsewhere rather than as the search itself. Is that ZenML-specific, or does any run-tracking tool do it, and does the shape of the tracking matter?

**Design.** Five arms of the same research-loop task (`shared/projects/research`, the `r1-clock` variant's rules): plain scripts (the existing `research_bare`), ZenML (existing), Prefect, Metaflow, Airflow. Same data, same seeds, same 12-run budget, same stated 25-minute clock, same instruction modulo the tool's name and entrypoint. Bare condition only (no skills) unless every arm gets an equivalent skill. Codex only under the model budget rule; ≥10 trials per arm, sequential (`-n 1`), since the existing effect is n=5.

**What transfers and what does not.** Only the research-loop family transfers; build-and-fix tasks are ZenML bugs. Three of the four frameworks have no model registry, so "promote to production" becomes the bare variant's file-path contract in those arms. The grader must be framework-neutral: load the promoted model from the stated contract, score on hidden data, read the training-slice fingerprint (`n_train_rows`/digest) from the run record or results file. Per-framework evidence rules (three seeds linked to a version) are dropped for this study or given per-arm equivalents.

**Pre-registered metrics** (decide before running, report all): hidden log loss of the promoted model; `gap_closed`; minutes to first recorded experiment; runs/rows spent; off-loop scripts; share of promotions backed by ≥3 seeds; tokens and cost. Read four trajectories per arm by hand for the "what did a run mean to the agent" question.

**Confounds to state, not remove.** Pretraining familiarity differs (Airflow and Prefect are far more common in training data than ZenML or Metaflow); each arm needs an offline docs snapshot of the same vintage in its image; per-run cost differs by framework (Airflow's scheduler overhead is real) and must be measured and reported, since the clock variant makes it bind.

**Cost.** About $0.50 per Codex trial; 5 arms × 10 trials ≈ $25 per harness. Two to three days of work, most of it writing the four projects and their images.

**Not for the benchmark.** A benchmark rewards a policy for using ZenML well; this study asks a different question. Keep it under `experiments/framework-comparison/`, results in `experiments/framework-comparison/RESULTS.md`, not in `results/` and not on the Hubs.

## 2. Codex-only replication of the ZenML vs bare effect (cheap, do first)

Ten more Codex trials per variant on `r1-clock` and `r1-bare-clock`, sequential. About $5. Decides whether experiment 1 is worth building: if the n=15 effect vanishes, the framework comparison has no hypothesis to test.

## 3. Task images in a registry for hosted Prime sandboxes

`prime env install zenml/zenml-bench` works locally after `scripts/build_task_images.sh`; Prime's hosted sandboxes need the 18 images in a registry (e.g. `ghcr.io/zenml-io/zenml-bench-<task>:0.1.0`) and the wrapper's `image_template` pointed there. Needs a registry push (Alex's to run) and a wrapper re-push.

## 4. Training run (see `docs/research-rl-training.md` §6)

After the Qwen baseline says where the floor is: curriculum from the generated instances, `harbor_rl` or Prime Lab, Qwen3.5-9B. Gated on experiment findings in `results/small-models.md`.
