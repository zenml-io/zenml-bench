#!/usr/bin/env bash
# usage: scripts/check_public.sh [jobs/<job> ...]
# Run before making anything public: scans tracked files + full git history, and any job dirs given, for
# secrets and personal data. Prints counts only, never values. Exit 1 if anything is found.
#
# Why the key regex needs a boundary: Codex session logs contain `encrypted_content` blobs (base64 of the model's
# encrypted reasoning) in which `sk-` followed by 20+ base64 chars occurs by chance. A bare `sk-…` regex fires on
# those (14 false positives on 2026-09-10); anchoring on a preceding quote/space/=/: does not.
set -uo pipefail
cd "$(dirname "$0")/.."
KEY='(^|["'"'"' =:,])(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|ghp_[A-Za-z0-9]{30,})'
ENVVAL='(OPENAI|ANTHROPIC|OPENROUTER|AWS_SECRET_ACCESS|GITHUB)_[A-Z_]*(KEY|TOKEN)["'"'"']?[=:] *["'"'"']?[A-Za-z0-9]'
PERSONAL='/Users/[a-z]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(io|com|nl|org)'
bad=0
report() { local n="$1" what="$2"; printf '%-58s %s\n' "$what" "$n"; [ "$n" -gt 0 ] && bad=1; }
report "$(git grep -lE "$KEY" 2>/dev/null | wc -l | tr -d ' ')" "tracked files with key-shaped strings"
report "$(git grep -lE "$ENVVAL" 2>/dev/null | wc -l | tr -d ' ')" "tracked files with a key env var + value"
report "$(git grep -lE "$PERSONAL" 2>/dev/null | wc -l | tr -d ' ')" "tracked files with home paths or emails"
report "$(git grep -cE "$KEY" $(git rev-list --all) 2>/dev/null | wc -l | tr -d ' ')" "history blobs with key-shaped strings"
report "$(git log --all --oneline -- .env design .skills-cache jobs 2>/dev/null | wc -l | tr -d ' ')" "commits touching .env/design/jobs/.skills-cache"
for j in "$@"; do
  report "$(grep -rIlE "$KEY" "$j" 2>/dev/null | wc -l | tr -d ' ')" "$j: files with key-shaped strings"
  report "$(grep -rIlE "$ENVVAL" "$j" 2>/dev/null | wc -l | tr -d ' ')" "$j: files with a key env var + value"
  report "$(grep -rIlE "$PERSONAL" "$j" 2>/dev/null | wc -l | tr -d ' ')" "$j: files with home paths or emails"
done
[ "$bad" -eq 0 ] && echo "clean" || { echo "FOUND something: inspect with the same regexes before publishing"; exit 1; }
