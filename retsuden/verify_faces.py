#!/usr/bin/env python3
"""Verify the portrait decoding (rom.face_pixels) against the game: for every portrait n, copy its entries into
劉備's slot (204) of the portrait tables, open 劉備's status screen in MAME and compare the 48x64 portrait on
screen pixel by pixel (eyes open or closed, since they blink). The Chinese version takes the same key presses.

Usage: .venv/bin/python retsuden/verify_faces.py [--rom ROM] [--faces 0,1,204]   # Japanese (default) or Chinese ROM
"""
import argparse
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from replay import replay

# Title → 1 player → settings (189年, Liu Bei) → first turn → 状況視察 → person list (劉備 highlighted), by version:
# the Chinese one takes longer to start the first turn
BOOT = {r: ("w900 start:10 w120 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w300 "
            f"c:10 w300 c:10 w300 w300 c:10 w300 w{wait} c:10 w300 c:10 w300 c:10 w120 c:10 w120")
        for r, wait in (("J", 1500), ("C", 2100))}
SLOT = 204
SCREEN_X, SCREEN_Y = 16, 8


def patch_for(rom: bytes, n: int) -> list[tuple[int, bytes]]:
    """ROM patches that make portrait slot SLOT show portrait n."""
    out = []
    f = R.layout(rom).face_map
    for base, size in ((f + R.FACE_MAP, 96), (f + R.FACE_EYES, 16), (f + R.FACE_MOUTH, 8), (f + R.FACE_PAL_INDEX, 1)):
        out.append((base + SLOT * size, rom[base + n * size:base + n * size + size]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--faces", help="只驗證這些頭像號（逗號分隔）")
    args = ap.parse_args()
    rom = R.load(args.rom)
    faces = [int(x) for x in args.faces.split(",")] if args.faces else list(range(R.N_FACES))
    runs = [{"rom": patch_for(rom, n), "steps": "c:10 w120", "at": 130, "shot": True} for n in faces]
    results = replay(args.rom, BOOT[R.layout(rom).region], runs)
    bad = []
    for n, res in zip(faces, results):
        scr = Image.open(res["shot"]).convert("RGB")
        pal = [R.md_rgb(w) for w in R.face_palette(rom, n)]
        ok = False
        for eyes in (0, 1):
            px = R.face_pixels(rom, n, eyes=eyes)
            diff = sum(scr.getpixel((SCREEN_X + x, SCREEN_Y + y)) != pal[c]
                       for y, row in enumerate(px) for x, c in enumerate(row))
            ok = ok or diff == 0
        if not ok:
            bad.append(n)
    print(f"portraits {len(faces) - len(bad)}/{len(faces)} identical" + (f"; mismatched: {bad}" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
