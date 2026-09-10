# /// script
# requires-python = ">=3.14"
# ///
"""Regenerates data/<date>.csv for 2026-09-06..09 and fixtures/hidden.csv. Deterministic.

Amounts of 1000 or more are written the way the upstream export writes them: with a thousands separator
("1,234.50"), quoted. Only 2026-09-09 and the hidden fixture contain such rows.
"""
import csv
import random
from pathlib import Path

HERE = Path(__file__).parent
REGIONS = ["north", "south", "east", "west"]


def fmt(amount: float) -> str:
    return f"{amount:,.2f}" if amount >= 1000 else f"{amount:.2f}"


def day(date: str, seed: int, n: int, big_rows: dict[int, float]) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        amount = big_rows.get(i, round(rng.uniform(5, 950), 2))
        hh, mm, ss = rng.randint(8, 19), rng.randint(0, 59), rng.randint(0, 59)
        rows.append({"id": f"{date.replace('-', '')}-{i:03d}", "ts": f"{date} {hh:02d}:{mm:02d}:{ss:02d}",
                     "region": rng.choice(REGIONS), "amount": fmt(amount)})
    return rows


def write(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "ts", "region", "amount"], quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    write(HERE / "data" / "2026-09-06.csv", day("2026-09-06", 6, 38, {}))
    write(HERE / "data" / "2026-09-07.csv", day("2026-09-07", 7, 41, {}))
    write(HERE / "data" / "2026-09-08.csv", day("2026-09-08", 8, 44, {}))
    write(HERE / "data" / "2026-09-09.csv", day("2026-09-09", 9, 46, {3: 1234.5, 17: 2000.0, 29: 1050.25}))
    write(HERE / "fixtures" / "hidden_plain.csv", day("2026-08-30", 30, 35, {}))
    write(HERE / "fixtures" / "hidden.csv", day("2026-08-31", 31, 52, {0: 12000.0, 8: 1000.0, 21: 3499.99, 40: 1500.5, 51: 9999.01}))
    # B14's hand-run backfill of late August (no separator amounts; that fault first appears on 2026-09-09)
    for date, seed, n in (("2026-08-24", 24, 30), ("2026-08-25", 25, 38), ("2026-08-26", 26, 60), ("2026-08-27", 27, 34)):
        write(HERE / "fixtures" / "backfill" / f"{date}.csv", day(date, seed, n, {}))
    # B14H's backfill (fixtures/backfill_hard/): three days were processed twice because finance sent corrected
    # exports (<date>.v2.csv). Totals are chosen so that every wrong rule picks a different run than the right one:
    #   right rule (latest COMPLETED processing per day, then largest total)      -> 08-26 v2
    #   largest total among completed backfill runs (ignores "superseded")        -> 08-27 v1
    #   largest total among all summary artifacts (ignores run status)           -> 08-26 v1 (failed in write_report)
    #   latest processing per day regardless of status, then largest total       -> 08-25 v2 (failed in write_report)
    def find(date, n, lo, hi, start):
        for seed in range(start, start + 500):
            rows = day(date, seed, n, {})
            total = sum(float(r["amount"]) for r in rows)
            if lo <= total <= hi:
                return rows, round(total, 2)
        raise SystemExit(f"no seed for {date} in [{lo}, {hi}]")
    hard = {
        "2026-08-24.csv": find("2026-08-24", 26, 11500, 12500, 2400),
        "2026-08-25.csv": find("2026-08-25", 34, 16000, 16250, 2500),      # completed
        "2026-08-25.v2.csv": find("2026-08-25", 36, 16800, 17000, 2550),   # corrected export, run failed in write_report
        "2026-08-26.csv": find("2026-08-26", 36, 17100, 17400, 2600),      # failed in write_report; largest summary of all
        "2026-08-26.v2.csv": find("2026-08-26", 35, 16400, 16600, 2650),   # completed: the answer
        "2026-08-27.csv": find("2026-08-27", 35, 16650, 16750, 2700),      # completed, then superseded by v2
        "2026-08-27.v2.csv": find("2026-08-27", 31, 14800, 15200, 2750),   # completed
    }
    for name, (rows, total) in hard.items():
        write(HERE / "fixtures" / "backfill_hard" / name, rows)
        print(f"  backfill_hard/{name}: {len(rows)} rows, total {total}")
    print("wrote data/2026-09-0{6,7,8,9}.csv, fixtures/hidden*.csv, fixtures/backfill/*.csv and fixtures/backfill_hard/*.csv")
