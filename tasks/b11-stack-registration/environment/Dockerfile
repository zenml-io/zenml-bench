FROM zenml-bench/base:0.96.4
# The base image has no AWS/S3 integration packages; the `aws` service connector type and the `s3` artifact
# store flavour need them (zenml integration requirements aws / s3). Installed here so the sealed container
# can register the components without network.
RUN pip install "s3fs>2022.3.0,!=2025.3.1" boto3 aws-profile-manager
# stack_onboarding/ is synced from shared/projects/stack_onboarding by scripts/sync_project.sh; do not edit it here.
COPY stack_onboarding /app/stack_onboarding
WORKDIR /app/stack_onboarding
RUN zenml init
