# Base image for every zenml-bench task. The ZenML pin lives HERE and nowhere else.
ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim
ARG ZENML_PIN=0.96.4
ENV ZENML_PIN=${ZENML_PIN} \
    ZENML_ANALYTICS_OPT_IN=false \
    ZENML_LOGGING_VERBOSITY=WARNING \
    PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends bash curl git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install "zenml[local]==${ZENML_PIN}" pandas scikit-learn pytest
# Offline documentation snapshot. TODO(decisions): pin to the docs matching ZENML_PIN rather than "latest".
ADD https://docs.zenml.io/llms-full.txt /opt/zenml-docs/llms-full.txt
RUN chmod -R a+r /opt/zenml-docs
