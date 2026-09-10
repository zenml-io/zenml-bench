# /// script
# requires-python = ">=3.14"
# ///
"""Regenerates the hard variant's exports and fixtures. Deterministic.

data/            the clean days still on the box at agent time
fixtures/exports the days used only to produce history at image build (then quarantined/rotated away)
fixtures/hidden_*.csv  the grader's unseen exports, one per fault class, one clean, one with both

Fault classes, as the upstream export produces them:
- separators: amounts of 1000 or more written as "1,234.50" (quoted)
- regions: region names capitalised or padded ("North", "west ") instead of lowercase
- iso_ts: timestamps written as 2026-08-30T08:21:32 (an older export format; the manual-run distractor)
"""
import csv
import random
from pathlib import Path

HERE = Path(__file__).parent
REGIONS = ["north", "south", "east", "west"]


def fmt(amount: float) -> str:
    return f"{amount:,.2f}" if amount >= 1000 else f"{amount:.2f}"


def day(date: str, seed: int, n: int, big_rows: dict[int, float] = {}, region_rows: dict[int, str] = {}, iso_ts: bool = False) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        amount = big_rows.get(i, round(rng.uniform(5, 950), 2))
        hh, mm, ss = rng.randint(8, 19), rng.randint(0, 59), rng.randint(0, 59)
        region = rng.choice(REGIONS)
        sep = "T" if iso_ts else " "
        rows.append({"id": f"{date.replace('-', '')}-{i:03d}", "ts": f"{date}{sep}{hh:02d}:{mm:02d}:{ss:02d}",
                     "region": region_rows.get(i, region), "amount": fmt(amount)})
    return rows


def write(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "ts", "region", "amount"], quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    data, exp, fix = HERE / "data", HERE / "fixtures" / "exports", HERE / "fixtures"
    write(data / "2026-09-02.csv", day("2026-09-02", 902, 40))
    write(data / "2026-09-04.csv", day("2026-09-04", 904, 37))
    write(data / "2026-09-06.csv", day("2026-09-06", 906, 38))
    write(data / "2026-09-07.csv", day("2026-09-07", 907, 41))
    write(data / "2026-09-08.csv", day("2026-09-08", 908, 44))
    write(exp / "2026-08-30.csv", day("2026-08-30", 830, 33, iso_ts=True))
    write(exp / "2026-09-03.csv", day("2026-09-03", 903, 41, region_rows={5: "North", 12: "west ", 30: "North"}))
    write(exp / "2026-09-09.csv", day("2026-09-09", 909, 46, big_rows={3: 1234.5, 17: 2000.0, 29: 1050.25}))
    write(fix / "hidden_plain.csv", day("2026-08-20", 820, 35))
    write(fix / "hidden_sep.csv", day("2026-08-21", 821, 52, big_rows={0: 12000.0, 8: 1000.0, 21: 3499.99, 40: 1500.5, 51: 9999.01}))
    write(fix / "hidden_region.csv", day("2026-08-22", 822, 39, region_rows={0: "EAST", 7: " south", 19: "West", 38: "SOUTH "}))
    write(fix / "hidden_both.csv", day("2026-08-23", 823, 47, big_rows={2: 1100.0, 44: 2750.75}, region_rows={2: "North ", 11: "east "}))
    print("wrote data/, fixtures/exports/ and fixtures/hidden_*.csv")
