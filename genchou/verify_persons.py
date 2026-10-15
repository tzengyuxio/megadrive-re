#!/usr/bin/env python3
"""Verify the person fields (rom.person) against the game: for every person record of the 4 scenarios and the
family blocks, write its bytes +15..+18 (体力, 政治/戦闘, 魅力/指揮, 年齢) into Temujin's RAM record ($FF0002)
in MAME, open Info → Ruler and read the panel back from the nametable ($E000; the 8x16 font has the upper half of
character c at tile $40 + 2 * (c - $20)).

Usage: .venv/bin/python genchou/verify_persons.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from replay import replay

# new game, scenario 1, all defaults → first turn; command menu → Info → (Nation Data) → Ruler highlighted
BOOT = ("w1100 start:10 w200 start:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 "
        "c:10 w300 c:10 w300 c:10 w300 c:10 w100 down:10 w40 down:10 w40 down:10 w40 right:10 w40 c:10 w100 "
        "c:10 w100 right:10 w40 down:10 w40")
NAMETABLE = 0xE000
GRADES = "EDCBA"
# field → (row, first column, width) on the Ruler panel
CELLS = {"pol": (2, 22, 1), "war": (4, 22, 1), "lead": (2, 29, 1), "cha": (4, 29, 1), "body": (6, 21, 5),
         "age": (8, 21, 3)}


def read_text(nt: bytes, row: int, col: int, width: int) -> str:
    out = ""
    for x in range(col, col + width):
        t = (nt[(row * 32 + x) * 2] << 8 | nt[(row * 32 + x) * 2 + 1]) & 0x7FF
        out += chr(0x20 + (t - 0x40) // 2) if 0x40 <= t < 0x100 and t % 2 == 0 else "?"
    return out.replace(" ", "")


def main() -> None:
    ap = argparse.ArgumentParser(description="人物欄位的模擬器驗證（Info → Ruler）")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.load(args.rom)
    records = {}                         # distinct (+15..+18) → a person using it
    for n in range(R.SCENARIO_COUNT):
        a = R.block_a(rom, n)
        for p in R.persons(rom, n):
            off = R.PERSONS_AT + R.PERSON_SIZE * p["slot"]
            records.setdefault(a[off + 15:off + 19], p)
        for f in R.families(rom, n):
            for p in f["persons"]:
                off = f["address"] + R.PERSON_SIZE * p["slot"]
                records.setdefault(rom[off + 15:off + 19], p)
    keys = list(records)
    runs = [{"ram": [(0xFF0000 + R.PERSONS_AT + 15, k)], "steps": "c:10 w100", "at": 100,
             "read": [("vram", NAMETABLE, 10 * 64)]} for k in keys]
    results = replay(args.rom, BOOT, runs)
    bad = []
    for k, res in zip(keys, results):
        p = R.person(bytes(15) + k + bytes(5))
        want = {f: GRADES[p[f]] for f in ("pol", "war", "lead", "cha")}
        want["body"] = f"{p['hp']}/{p['hp_max']}"
        want["age"] = str(p["age"])
        got = {f: read_text(res["read"][0], *c) for f, c in CELLS.items()}
        if got != want:
            bad.append(f"{records[k]['name']} {k.hex()}: {got} ≠ {want}")
    print(f"person records {len(keys) - len(bad)}/{len(keys)} distinct value sets match "
          f"(政治 戦闘 指揮 魅力 体力 年齢)")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
