#!/usr/bin/env python3
"""Verify what the person fields mean: for every person n of the 189 scenario, write n's values (rom.ram_image)
into 関羽's RAM slot, open his status screen in MAME and read the numbers back from the plane A nametable
(digit tiles $270-$279, level digits $2BC + 4*d). 体力 is written as 体力上限 - (n % 7) so that the two 体力
numbers can be told apart. The Chinese version has the same screen layout and key presses.

Usage: .venv/bin/python retsuden/verify_persons.py [--rom ROM] [--persons 0,1,2]   # Japanese (default) or Chinese
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from replay import replay
from verify_faces import BOOT

SLOT = 39  # 関羽: second in 劉備's list, neither ruler nor governor, so 忠誠度 is shown
PLANE_A = 0xC000
# field → (row, column of the last digit) on the status screen
POSITIONS = {"hp": (13, 12), "hp_max": (15, 12), "war": (19, 12), "int": (22, 12), "virtue": (25, 12),
             "loyalty": (13, 24), "lead": (16, 24), "mobility": (19, 24), "soldiers": (22, 24), "morale": (25, 24),
             "civil": (8, 26), "military": (8, 37), "attack1": (13, 37), "attack2": (16, 37)}
WORD_FIELDS = {"hp_max": 0xB000, "hp": 0xB200, "war": 0xB400, "int": 0xB600, "lead": 0xB800, "civil": 0xBE00,
               "military": 0xC000}
BYTE_FIELDS = {"virtue": 0xC200, "loyalty": 0xC300, "mobility": 0xC400, "morale": 0xC500, "level": 0xC600}


def number_at(nt: bytes, row: int, col: int) -> int | None:
    """The number whose last digit is at (row, col) of a 64-cell-wide nametable."""
    digits = ""
    while col >= 0:
        t = (nt[(row * 64 + col) * 2] << 8 | nt[(row * 64 + col) * 2 + 1]) & 0x7FF
        if not 0x270 <= t <= 0x279:
            break
        digits = str(t - 0x270) + digits
        col -= 1
    return int(digits) if digits else None


def level_at(nt: bytes) -> int:
    t = (nt[(1 * 64 + 24) * 2] << 8 | nt[(1 * 64 + 24) * 2 + 1]) & 0x7FF
    return (t - 0x2BC) // 4


def main() -> None:
    ap = argparse.ArgumentParser(description="人物欄位的模擬器驗證（狀態畫面）")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--persons", help="只驗證這些人物（逗號分隔）")
    args = ap.parse_args()
    rom = R.load(args.rom)
    sc = R.scenario(rom, 0)
    people = [int(x) for x in args.persons.split(",")] if args.persons else list(range(R.N_PERSONS))
    runs, expected = [], []
    for n in people:
        v = {f: sc[f][n] for f in list(WORD_FIELDS) + list(BYTE_FIELDS)}
        v["hp"] = max(v["hp_max"] - n % 7, 0)
        v["virtue"] = min(v["virtue"], 100)  # the status screen caps 徳 at 100 ($B7A4)
        ram = [(0xFF0000 + a + SLOT * 2, v[f].to_bytes(2, "big")) for f, a in WORD_FIELDS.items()]
        ram += [(0xFF0000 + a + SLOT, bytes([v[f]])) for f, a in BYTE_FIELDS.items()]
        ram.append((0xFFC800 + SLOT * 4, sc["soldiers"][n].to_bytes(4, "big")))
        ram.append((0xFFEA88 + SLOT * 3, bytes(sc["weapons"][n])))
        runs.append({"ram": ram, "steps": "c:10 w120", "at": 130, "read": [("vram", PLANE_A, 28 * 128)]})
        a1, a2 = R.attack(v["war"], v["morale"], sc["weapons"][n], rom)
        expected.append({**v, "soldiers": sc["soldiers"][n], "attack1": a1, "attack2": a2})
    results = replay(args.rom, BOOT[R.layout(rom).region] + " down:6 w30", runs)
    bad = []
    for n, want, res in zip(people, expected, results):
        nt = res["read"][0]
        got = {f: number_at(nt, *pos) for f, pos in POSITIONS.items()}
        got["level"] = level_at(nt)
        wrong = [f"{f} {got[f]}≠{want[f]}" for f in got if got[f] != want[f] and not (want[f] == 0 and got[f] is None)]
        if wrong:
            bad.append(f"{n}: {', '.join(wrong)}")
    print(f"persons {len(people) - len(bad)}/{len(people)}: all {len(POSITIONS) + 1} numbers match")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
