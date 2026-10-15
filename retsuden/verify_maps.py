#!/usr/bin/env python3
"""Verify the strategic map decoding (rom.strategic_map) against the game: start the 189 scenario in MAME, scroll the
map around with the pad and, at every stop, take the 40x28 cells of plane B on screen (through the scroll registers)
and find them in the decoded map. Every cell must match at one map position.

Usage: .venv/bin/python retsuden/verify_maps.py [--rom ROM]   # Japanese (default) or Chinese ROM
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from drive import events_lua, schedule
from mame import run
from verify_scenarios import boot

# a tour of the map: to the top left corner, then rows of short moves (zigzag), a dump after each
MOVES = ["up:300 left:300"] + [m for band in range(6) for m in
                               [("right:80" if band % 2 == 0 else "left:80")] * 4 + ["down:60"]]


def visible(vram: bytes, vsram: bytes, regs: bytes) -> np.ndarray:
    """28x40 nametable words of plane B as shown (whole-screen scroll; cells partly on screen count)."""
    base = (regs[4] & 7) << 13
    width = (32, 64, 64, 128)[regs[16] & 3]
    height = (32, 64, 64, 128)[regs[16] >> 4 & 3]
    hs_base = (regs[13] & 0x3F) << 10
    hscroll = int.from_bytes(vram[hs_base + 2:hs_base + 4], "big") & 0x3FF
    vscroll = int.from_bytes(vsram[2:4], "big") & 0x3FF
    x0, y0 = (-hscroll) % (width * 8) // 8, vscroll % (height * 8) // 8
    out = np.zeros((28, 40), np.int64)
    for y in range(28):
        for x in range(40):
            a = base + (((y0 + y) % height) * width + (x0 + x) % width) * 2
            out[y, x] = int.from_bytes(vram[a:a + 2], "big")
    return out


def locate(grid: np.ndarray, win: np.ndarray) -> tuple[int, int, int]:
    """(best match count, row, column) of win in grid."""
    best = (-1, 0, 0)
    h, w = win.shape
    for y in range(grid.shape[0] - h + 1):
        for x in range(grid.shape[1] - w + 1):
            if grid[y, x] != win[0, 0]:
                continue
            m = int((grid[y:y + h, x:x + w] == win).sum())
            if m > best[0]:
                best = (m, y, x)
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description="大地圖的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.load(args.rom)
    grid = np.array(R.strategic_map(rom), np.int64)
    steps = boot(0) + " @s0 " + " ".join(f"{m} w30 @s{k + 1}" for k, m in enumerate(MOVES))
    events, end = schedule(steps.split())
    seen = np.zeros(grid.shape, bool)
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        run(args.rom, events_lua(events, f"{tmp}/m", end, True))
        for k in range(len(MOVES) + 1):
            p = f"{tmp}/m_s{k}"
            vram, vsram, regs = (Path(f"{p}.{e}").read_bytes() for e in ("vram", "vsram", "regs"))
            win = visible(vram, vsram, regs)
            m, y, x = locate(grid, win)
            seen[y:y + 28, x:x + 40] = True
            bad += m != win.size
            print(f"stop {k}: map cell ({x}, {y}): {m}/{win.size} cells match")
    print(f"{seen.sum()}/{seen.size} map cells covered; {'all stops match' if not bad else f'{bad} stops differ'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
