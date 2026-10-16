#!/usr/bin/env python3
"""Verify the person table against the game: from "Select side." the C button opens George Washington's page
($1C7D4 → $1C6DC with person 238), which prints Leadership (record +28), Tactics (+29), Discipline (+30),
Reputation (person state +6 in the 1775 scenario RAM) and draws the face (record +34). For every person i the ROM is
patched so that the page shows person i instead of 238 (the two `move.l #$EE,D0` at $1C83C / $1C854); then the
four numbers read back from plane A (8x16 ASCII text, tile 2 (c - 0x20) on top) must be the decoded ones and VRAM
$D080 (30 tiles) must be rom.face_raw(face code).

Health (record +27) and the name are not on this page (the name is drawn in a proportional font) and are not checked.

Usage: .venv/bin/python dokuritsu/verify_persons.py [--quick]
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as L
from replay import replay
from verify_faces import BOOT, VRAM_FACE

PATCH_AT = [0x1C83E, 0x1C856]         # long immediates of move.l #$EE,D0 (person id for the page)
PLANE_A = 0xE000                      # 32 x 32 cells
ROWS = {9: ("Leadership", "Tactics"), 11: ("Reputation", "Discipline")}


def text_row(nt: bytes, row: int) -> str:
    s = ""
    for c in range(32):
        t = (nt[2 * (32 * row + c)] << 8 | nt[2 * (32 * row + c) + 1]) & 0x7FF
        s += chr(0x20 + t // 2) if t < 0xC0 and t % 2 == 0 else "?"
    return s


def main() -> None:
    ap = argparse.ArgumentParser(description="人物資料的模擬器驗證")
    ap.add_argument("--quick", action="store_true", help="只抽樣")
    args = ap.parse_args()
    rom = L.Rom()
    persons, states = rom.persons(), rom.person_states()
    ids = list(range(L.PERSON_COUNT))[::25] if args.quick else list(range(L.PERSON_COUNT))
    runs = [{"rom": [(a, i.to_bytes(4, "big")) for a in PATCH_AT], "steps": "c:20 w300", "at": 340,
             "read": [("vram", PLANE_A, 2048), ("vram", VRAM_FACE, L.FACE_BYTES)]} for i in ids]
    bad = []
    for i, res in zip(ids, replay(rom.path, BOOT + " c:20 w300", runs)):
        nt, face = res["read"]
        got = {}
        for row, keys in ROWS.items():
            nums = re.findall(r"\d+", text_row(nt, row))
            got.update(zip(keys, map(int, nums)))
        p = persons[i]
        want = {"Leadership": p["Leadership"], "Tactics": p["Tactics"], "Discipline": p["Discipline"],
                "Reputation": states[i]["reputation"]}
        errs = [f"{k} {got.get(k)} != {v}" for k, v in want.items() if got.get(k) != v]
        if face != rom.face_raw(p["face"]):
            errs.append(f"face {p['face']:04X}")
        if errs:
            bad.append(f"{i} {p['name']}: {', '.join(errs)}")
    print(f"persons {len(ids) - len(bad)}/{len(ids)}: Leadership, Tactics, Discipline, Reputation on screen and the "
          f"face in VRAM match")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
