#!/usr/bin/env python3
"""Verify the country fields (rom.countries) against the game: for every country record of the 4 scenarios,
write its 金 食糧 人口 (+10..+15) and the 3 values +21..+23 into Onon River's RAM record ($FF0000 +
Layout.countries_at) in MAME just before the first turn starts, and read the country panel of the main screen back
from the nametable (same cells in both versions).

Usage: .venv/bin/python genchou/verify_countries.py [--rom ROM]   # Japanese (default) or USA ROM
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from replay import replay
from verify_persons import NAMETABLE, TITLE, read_text

# new game, scenario 1, all defaults → "Is everything OK?"
BOOT = "start:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w300"
# field → (row, first column, width) on the country panel; numbers are right-aligned, gold and food are
# followed by the expected change ("369-60")
CELLS = {"gold": (20, 5, 6), "food": (22, 5, 6), "population": (24, 5, 6), "v21": (20, 19, 4),
         "v22": (22, 19, 4), "v23": (24, 19, 4)}


def leading_number(s: str) -> int | None:
    digits = ""
    for c in s.lstrip("?"):  # "?" = icon tiles left of the number
        if not c.isdigit():
            break
        digits += c
    return int(digits) if digits else None


def main() -> None:
    ap = argparse.ArgumentParser(description="國欄位的模擬器驗證（主畫面國資訊）")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.load(args.rom)
    L = R.layout(rom)
    onon = 0xFF0000 + L.countries_at
    rows = [(n, c) for n in range(R.SCENARIO_COUNT) for c in R.countries(rom, n)]
    runs = []
    for n, c in rows:
        rec = R.block_a(rom, n)[L.countries_at + R.COUNTRY_SIZE * c["id"]:][:R.COUNTRY_SIZE]
        runs.append({"ram": [(onon + 10, rec[10:16]), (onon + 21, rec[21:24])], "steps": "c:10 w300", "at": 300,
                     "read": [("vram", NAMETABLE, 28 * 64)]})
    results = replay(args.rom, TITLE[L.region] + BOOT, runs)
    bad = []
    for (n, c), res in zip(rows, results):
        got = {f: leading_number(read_text(res["read"][0], *cell, L.region)) for f, cell in CELLS.items()}
        want = {f: c[f] for f in CELLS}
        if got != want:
            bad.append(f"scenario {n + 1} country {c['id']}: {got} ≠ {want}")
    print(f"countries {len(rows) - len(bad)}/{len(rows)}: 金 食糧 人口 and the 3 values match")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
