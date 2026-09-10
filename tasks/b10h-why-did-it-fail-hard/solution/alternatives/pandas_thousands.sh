#!/usr/bin/env bash
# Alternative: tell the CSV reader about the separator (`thousands=","`) in `load`, and normalise the region
# names inside `summarise` instead of `parse`.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    return pd.read_csv(f"data/{date}.csv")'; assert old in s
s = s.replace(old, '    return pd.read_csv(f"data/{date}.csv", thousands=",")')
old = '        for region, g in df.groupby("region")["amount"]'; assert old in s
s = s.replace(old, '        for region, g in df.groupby(df["region"].str.strip().str.lower())["amount"]')
old = '        unknown = sorted(set(df["region"]) - set(REGIONS))'; assert old in s
s = s.replace(old, '        unknown = sorted(set(df["region"].str.strip().str.lower()) - set(REGIONS))')
p.write_text(s)
PY
for f in data/*.csv; do d="$(basename "$f" .csv)"; python run.py --date "$d"; done
