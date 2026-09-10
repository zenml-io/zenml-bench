# Baseline — task B11 `stack-registration`

Date: 2026-09-10. Frontier tier only, bare condition, 3 attempts per cell (Harbor 0.22.0, sealed network with the model API allowlisted, `-n 2`). Raw rows: `b11-stack-registration-baseline-l2.jsonl`. The container has no route to AWS; the task is to register an S3 artifact store behind a placeholder AWS connector, a Kubernetes orchestrator, a container registry and a stack, make it the project's active stack, and leave `default` intact.

| harness | model | condition | pass rate | hit `register --connector` trap | fixed with `connect --no-verify` | read CLI source | read docs | median tokens | mean cost | mean minutes |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | 0/3 | 3/3 | 2/3 | 1/3 | 701k | $0.70 | 3.2 |
| codex | gpt-5.6-terra | bare | 3/3 | 3/3 | 3/3 | 2/3 | 3/3 | 438k | $0.25 | 2.5 |

## What they did

Every trial started with `zenml service-connector register --help` (and the other `register --help`s), which lists `--no-verify`; nobody needed the docs for it (the offline docs snapshot never mentions the flag). Two Codex trials first guessed `--aws_region` and got a "no such option" before switching to `--region`; one asked `zenml service-connector describe-type aws --auth-method secret-key` for the attribute names, which is the right tool.

All three Codex trials ran `zenml artifact-store register … --connector aws-platform --resource-id …` and hit the trap: registration verifies the connector against AWS STS, fails after ~12 s with "Could not connect to the endpoint URL", and leaves the store unlinked. All three then read `describe` output, saw no connector, and repaired it with `zenml artifact-store connect s3-artifacts --connector aws-platform --no-verify` (2/3 after reading `zenml/cli/stack_components.py` to confirm that `register` hardcodes verification). Claude Code never took the `--connector` route: all three went straight to `register` then `connect --no-verify`; two of them then read the CLI source and the AWS connector's `_canonical_resource_id` anyway to decide what resource id to record, and two also made the link a second time through `Client().update_stack_component(...)` to be sure.

Every trial set the stack from inside `/app/stack_onboarding` and printed `.zen/config.yaml` to confirm the repository-level active stack; nobody set it globally (`global_active_too` would be 0 for all six). Five of six ran `zenml stack set default && python run.py && zenml stack set prod-k8s` to prove the default stack still works, exactly the check the grader does with `ZENML_ACTIVE_STACK_ID`.

## Findings

1. **Saturated (6/6).** The intended difficulty (no docs for `--no-verify`; `register --connector` silently drops the link) is defeated by `--help` and by the error message, both of which are good enough for a frontier model. Harder variants: (a) remove the CLI from the picture by requiring the registration in a Python script the team will rerun (idempotent re-registration is where agents fail: `create_stack_component` has no connector argument and `EntityExistsError` on rerun); (b) a connector type whose `--no-verify` is not enough, e.g. the S3 flavour with `authentication_secret` instead of a connector, or an auth method with a required field that the help does not explain; (c) a real cluster-less Kubernetes check with a kubeconfig file that must be written and referenced.
2. **The `register --connector` trap costs Codex ~12 s and one extra step but does not mislead it**, because the CLI prints the STS error and `describe` shows no connector. A silent failure would be needed to bite; ZenML is not silent here. Docs item: the service-connector page should say that component `register --connector` always verifies and that `connect --no-verify` is the offline route.
3. **Both harnesses read the installed ZenML source when the help is ambiguous** (4/6 opened `cli/stack_components.py` or the AWS connector module), consistent with B7 and B10.
