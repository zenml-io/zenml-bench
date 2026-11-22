#!/usr/bin/env bash
# Verifier entrypoint. Harbor copies tests/ to /tests and runs this as root after the agent finishes.
set -uo pipefail
mkdir -p /logs/verifier
cd /tests
python grade.py > /logs/verifier/reward.txt 2> /logs/verifier/grader.log || echo 0 > /logs/verifier/reward.txt
[ -s /logs/verifier/reward.txt ] || echo 0 > /logs/verifier/reward.txt
exit 0
