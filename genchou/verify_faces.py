#!/usr/bin/env python3
"""Verify the face decoding (rom.face_tiles) against the game: for every face code, write it into Temujin's record
of scenario 1 in ROM, start a new game in MAME and compare the 30 tiles the menu screen puts in VRAM for
Temujin's face (tile $200, the first face slot), palette line 1 and the screenshot (every pixel of a colour
other than 0, which is transparent) with the decoding.

Codes: the 97 portraits (as person codes 0-0x60; women's codes are drawn as portrait code + 0x39 by $77CC) and
every composed-face code in the persons, family blocks and women.

Usage: .venv/bin/python genchou/verify_faces.py [--rom ROM] [--codes 0,16,85F8]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from PIL import Image
from replay import replay

BOOT = "w1100 start:10 w200"            # title screen, before the press that opens the new-game menu
STEPS = "start:10 w250"                 # loads scenario 1 ($26250) and draws Temujin ($7752) and Borchu
TEMUJIN_FACE = R.PERSONS_AT + 22        # slot 0 of block A
SCREEN_X, SCREEN_Y = 16, 8              # the face's nametable cells (2-6, 1-6) on screen


def codes_in_data(rom: bytes) -> list[int]:
    out = set()
    for n in range(R.SCENARIO_COUNT):
        out |= {p["face"] for p in R.persons(rom, n)}
        out |= {p["face"] for f in R.families(rom, n) for p in f["persons"]}
    out |= {w["face"] for w in R.women(rom)}
    return sorted(c for c in out if c & 0x8000)


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--codes", help="只驗證這些頭像碼（十六進位，逗號分隔）")
    args = ap.parse_args()
    rom = R.load(args.rom)
    codes = ([int(x, 16) for x in args.codes.split(",")] if args.codes
             else list(range(R.PORTRAIT_COUNT)) + codes_in_data(rom))
    at = R.be32(rom, R.SCENARIO_A) + TEMUJIN_FACE
    runs = [{"rom": [(at, c.to_bytes(2, "big"))], "steps": STEPS, "at": 250, "shot": True,
             "read": [("vram", 0x200 * 32, R.FACE_BYTES), ("cram", 32, 32)]} for c in codes]
    results = replay(args.rom, BOOT, runs)
    palette = rom[R.FACE_PALETTE:R.FACE_PALETTE + 32]
    bad = []
    for c, res in zip(codes, results):
        tiles, cram = res["read"]
        if tiles != R.face_tiles(rom, c):
            bad.append(f"{c:04X} tiles")
        if cram != palette:
            bad.append(f"{c:04X} palette")
        shot = Image.open(res["shot"]).convert("RGB")
        rgb = R.face_palette(rom)
        w = R.FACE_W * 8
        if any(v and shot.getpixel((SCREEN_X + i % w, SCREEN_Y + i // w)) != rgb[v]
               for i, v in enumerate(R.tiles_pixels(R.face_tiles(rom, c)))):
            bad.append(f"{c:04X} screen")
    n_portraits = sum(1 for c in codes if not c & 0x8000)
    print(f"faces {len(codes) - len({b.split()[0] for b in bad})}/{len(codes)} identical "
          f"({n_portraits} portraits, {len(codes) - n_portraits} composed codes)")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
