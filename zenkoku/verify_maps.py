#!/usr/bin/env python3
"""Verify the strategy map against the game: pick each of the 4 scenarios in MAME and, once the map is painted,
find rom.map_bitmap(s) (600 tiles) in VRAM and compare it byte by byte; CRAM line 3 must be MAP_PALETTE.

Usage: .venv/bin/python zenkoku/verify_maps.py [--rom ROM]   # Japan (default) or USA ROM
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as Z
from drive import events_lua, schedule
from mame import run
from verify_faces import TITLE


def main() -> None:
    ap = argparse.ArgumentParser(description="大地圖的模擬器驗證")
    ap.add_argument("--rom", default=Z.DEFAULT_ROM)
    args = ap.parse_args()
    rom = Z.Rom(args.rom)
    pal = b"".join(rom.u16(rom.L.map_palette + 2 * i).to_bytes(2, "big") for i in range(16))
    failed = 0
    for s in range(Z.SCENARIO_COUNT):
        events, end = schedule((TITLE + "c:10 w200 " + "down:6 w30 " * s + "c:10 w600").split())
        with tempfile.TemporaryDirectory() as tmp:
            run(args.rom, events_lua(events, f"{tmp}/m", end, False))
            vram, cram = Path(f"{tmp}/m.vram").read_bytes(), Path(f"{tmp}/m.cram").read_bytes()
        bm = rom.map_bitmap(s)
        at = vram.find(bm[:32 * Z.MAP_W])  # first tile row (sea and coast, the same in every scenario)
        same = sum(a == b for a, b in zip(bm, vram[at:at + len(bm)])) if at >= 0 else 0
        ok = same == len(bm) and cram[96:128] == pal
        failed += not ok
        print(f"scenario {s + 1}: bitmap at VRAM {at:#06x}, {same}/{len(bm)} bytes equal; palette "
              f"{'OK' if cram[96:128] == pal else 'NG'}")
    print("ALL OK" if not failed else f"{failed} scenario(s) differ")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
