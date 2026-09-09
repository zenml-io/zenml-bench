#!/usr/bin/env bash
# usage: scripts/sync_project.sh <project> <task-dir>
# Copies shared/projects/<project> into <task-dir>/environment/<project> so the Harbor task is self-contained.
# shared/projects/ is the source of truth; never edit the copy under environment/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/shared/projects/$1"; DST="$ROOT/$2/environment/$1"
rm -rf "$DST"; mkdir -p "$DST"
rsync -a --exclude .zen --exclude fixtures --exclude make_data.py --exclude '__pycache__' "$SRC/" "$DST/"
echo "synced $SRC -> $DST"
