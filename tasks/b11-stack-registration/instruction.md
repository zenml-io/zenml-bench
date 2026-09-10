The fraud-scoring team's project is in `/app/stack_onboarding` (a ZenML repository; `python run.py` from there runs the `smoke_check` pipeline on the active stack). It currently runs on the local `default` stack. The platform team has handed over the production infrastructure and wants it registered in ZenML on this machine, which has **no network access to AWS or the cluster**; the real credentials will be rotated in later by the platform team, so registration must not depend on reaching AWS.

Register the following, with exactly these names and values:

1. A service connector `aws-platform` of type `aws`, authentication method `secret-key`, region `eu-central-1`, with the placeholder credentials access key id `AKIAPLACEHOLDER000001` and secret access key `placeholder-secret-rotate-me`.
2. An artifact store `s3-artifacts` (S3 flavour) at `s3://ml-platform-artifacts/zenml`, connected to the bucket `ml-platform-artifacts` through the `aws-platform` connector. "Connected" means ZenML records the connector on the artifact store; a store that merely has an S3 path does not count.
3. An orchestrator `k8s-prod` (Kubernetes flavour) using kubeconfig context `prod-eks`, namespace `ml-prod`, and running pipelines asynchronously (`synchronous` off).
4. A container registry `ecr-prod` with URI `123456789012.dkr.ecr.eu-central-1.amazonaws.com`.
5. A stack `prod-k8s` made of exactly those three components, set as the active stack for the project in `/app/stack_onboarding` (so that `python run.py` run from there would target it).

Leave the `default` stack and its components untouched: they must still exist and `python run.py` must still complete when run on `default`. Do not try to run the pipeline on `prod-k8s`; there is no cluster. When you are done, `default` and `prod-k8s` must be the only stacks, and no components or connectors other than the ones above (plus the pre-existing defaults) should remain registered. The S3 and AWS integration packages are already installed. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
