#!/usr/bin/env python3
"""Verify the person fields (rom.person) against the game: for every person record of the 4 scenarios and the
family blocks, write its 体力, 政治/戦闘, 魅力/指揮, 年齢 bytes (name + 2..5) into Temujin's RAM record ($FF0002)
in MAME, open Info → Ruler (情報 → 君主) and read the panel back from the nametable ($E000; the 8x16 font has the
upper half of character k at tile $40 + 2k, k = c - $20 in the USA font and FONT_J.index(c) in the Japanese one).

Usage: .venv/bin/python genchou/verify_persons.py [--rom ROM]   # Japanese (default) or USA ROM
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from replay import replay

# new game, scenario 1, all defaults → first turn; command menu → Info → (Nation Data) → Ruler highlighted. Both
# versions take the same keys; the Japanese title takes Start later.
TITLE = {"J": "w1600 start:10 w200 ", "U": "w1100 start:10 w200 "}
BOOT = ("start:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 "
        "c:10 w300 c:10 w300 c:10 w300 c:10 w100 down:10 w40 down:10 w40 down:10 w40 right:10 w40 c:10 w100 "
        "c:10 w100 right:10 w40 down:10 w40")
NAMETABLE = 0xE000
FONT_J = " ()*+-./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"   # the Japanese 8x16 font from tile $40 (VRAM, by eye)
GRADES = "EDCBA"
# field → (row, first column, width) on the USA Ruler panel
CELLS = {"pol": (2, 22, 1), "war": (4, 22, 1), "lead": (2, 29, 1), "cha": (4, 29, 1), "body": (6, 21, 5),
         "age": (8, 21, 3)}


def read_text(nt: bytes, row: int, col: int, width: int, region: str = "U") -> str:
    out = ""
    for x in range(col, col + width):
        t = (nt[(row * 32 + x) * 2] << 8 | nt[(row * 32 + x) * 2 + 1]) & 0x7FF
        k = (t - 0x40) // 2
        if region == "J":
            out += FONT_J[k] if 0x40 <= t < 0x40 + 2 * len(FONT_J) and t % 2 == 0 else "?"
        else:
            out += chr(0x20 + k) if 0x40 <= t < 0x100 and t % 2 == 0 else "?"
    return out.replace(" ", "")


def main() -> None:
    ap = argparse.ArgumentParser(description="人物欄位的模擬器驗證（Info → Ruler）")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.load(args.rom)
    L = R.layout(rom)
    v = L.name_len + 2                   # 体力, 政治/戦闘, 魅力/指揮, 年齢
    records = {}                         # distinct values → a person using them
    for n in range(R.SCENARIO_COUNT):
        a = R.block_a(rom, n)
        for p in R.persons(rom, n):
            off = R.PERSONS_AT + L.person_size * p["slot"]
            records.setdefault(a[off + v:off + v + 4], p)
        for f in R.families(rom, n):
            for p in f["persons"]:
                off = f["address"] + L.person_size * p["slot"]
                records.setdefault(rom[off + v:off + v + 4], p)
    keys = list(records)
    runs = [{"ram": [(0xFF0000 + R.PERSONS_AT + v, k)], "steps": "c:10 w100", "at": 100,
             "read": [("vram", NAMETABLE, 10 * 64)]} for k in keys]
    results = replay(args.rom, TITLE[L.region] + BOOT, runs)
    bad = []
    for k, res in zip(keys, results):
        p = R.person(bytes(v) + k + bytes(L.person_size - v - 4), L)
        want = {f: GRADES[p[f]] for f in ("pol", "war", "lead", "cha")}
        want["body"] = f"{p['hp']}/{p['hp_max']}"
        want["age"] = str(p["age"])
        shift = 2 if L.region == "J" else 0          # the Japanese panel is 2 cells further left
        got = {f: read_text(res["read"][0], r, c - shift, w, L.region) for f, (r, c, w) in CELLS.items()}
        if got != want:
            bad.append(f"{records[k]['name']} {k.hex()}: {got} ≠ {want}")
    print(f"person records {len(keys) - len(bad)}/{len(keys)} distinct value sets match "
          f"(政治 戦闘 指揮 魅力 体力 年齢)")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
