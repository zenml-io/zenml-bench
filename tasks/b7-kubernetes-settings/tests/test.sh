#!/usr/bin/env bash
# Verifier entrypoint. Harbor copies tests/ to /tests and runs this after the agent finishes.
set -uo pipefail
mkdir -p /logs/verifier
cd "${APP_DIR:-/app/k8s_training}"
python -m pytest -q /tests -p no:cacheprovider --junitxml=/logs/verifier/junit.xml 2>&1 | tee /logs/verifier/pytest.log
status=${PIPESTATUS[0]}
if [ "$status" -eq 0 ]; then echo 1 > /logs/verifier/reward.txt; else echo 0 > /logs/verifier/reward.txt; fi
exit 0
