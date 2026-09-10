# Generated task instances

Everything in this directory is produced by `scripts/generate_instances.py`; do not edit an instance by hand, change the generator and regenerate (`--seed <n> --n 1` rebuilds one instance deterministically).

## What is here

Held-out instances, seeds 0–4 of each family, committed so that the benchmark's generated set is fixed and anyone can rebuild it byte for byte:

| family | generated from | what varies per seed | instances |
|---|---|---|---|
| `b10` | `tasks/b10-why-did-it-fail` | week dates, region names, the fault (thousands separator, region spelling, timestamp format, negative amounts in parentheses, an extra column), which distractor failures precede it, the typo run's date, run naming and tag scheme, pipeline and project name | `b10-gen-0000` … `b10-gen-0004` |
| `b3` | `tasks/b3-stale-cache` | pipeline, step and output names, data path and label column, whether the path is a pipeline parameter, which step is the expensive one (trainer or evaluator), split parameters, fixture data (seeds, size, noise) | `b3-gen-0000` … `b3-gen-0004` |

Each instance is a complete Harbor task: `instruction.md`, `task.toml` (`[metadata] generated_from`, `generator_seed`, `generator_params`), `environment/` (the generated project and, for b10, a `setup_store.sh` that produces the run history by really running the pipeline), `solution/solve.sh` with alternatives, and `tests/` with hidden fixtures, expected values produced by running the reference, the shortcuts (including `tamper_store.sh`) and `store_integrity.py`.

## Training instances

Regenerate as many as needed into `tasks/generated-train/` (gitignored), starting at seed 1000 so they never overlap the held-out set:

```bash
PATH=.venv/bin:$PATH .venv/bin/python scripts/generate_instances.py b10 --n 200 --seed 1000 --out tasks/generated-train
PATH=.venv/bin:$PATH .venv/bin/python scripts/generate_instances.py b3  --n 200 --seed 1000 --out tasks/generated-train
```

Generation runs the reference through ZenML for every instance (20–40 s each), so 400 instances take a few hours; the held-out set is enough to check a change to the templates. Grade an instance locally with `scripts/grade_local.sh tasks/generated/b10-gen-0000 [patch.sh]` and under Harbor with `uv run scripts/verify_task.py tasks/generated/b10-gen-0000`.

## Why hold out low seeds

A trainer that sees an instance's exact dates, names and fault learns that instance; the benchmark score must come from instances the policy never saw. Holding out a fixed seed range (rather than a random split recorded in a file) keeps the split reproducible from the script alone. The hand-written parents (`b10-why-did-it-fail`, `b3-stale-cache`) stay in the main benchmark table; generated instances are reported as a separate row per family.
