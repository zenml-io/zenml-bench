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
    print("wrote data/2026-09-0{6,7,8,9}.csv, fixtures/hidden*.csv and fixtures/backfill/*.csv")
