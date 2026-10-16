#!/usr/bin/env python3
"""Verify the portrait decoding against the game: scenario 1, 1 player, Allies; on the battle screen the game
draws アイゼンハワー (general record +0x14 = face 96) with $8388: LZ $3360 decodes the face from the pointer table
FACES, the tiles go to VRAM FACE_VRAM (tile 0x340) and FACE_PALETTE to CRAM line 0, and the face shows at screen
(200, 168). Every run starts from a savestate taken just before that, patches all 120 pointers of the table to
face n's stream, and then compares VRAM (960 bytes) with rom.face_tiles, CRAM line 0 with FACE_PALETTE and the
40x48 screen area with rom.face_rgb, pixel by pixel. Colour 0 is transparent on the MD (the window behind
shows), so pixels of colour 0 are left out of the screen comparison.

Usage: .venv/bin/python europe/verify_faces.py [--rom ROM] [--quick]
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
from verify_scenarios import DOWN, TITLE, TO_BATTLE

BOOT = TITLE + DOWN + TO_BATTLE.removesuffix(" w300 w600") + " w20"  # before the first face draw (~250 frames later)
AT = 400                                                             # face drawn (the next draw is ~f740)
FACE_X, FACE_Y = 200, 168


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="只驗證頭像 0、96、99、100、119")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    faces = [0, 96, 99, 100, 119] if args.quick else list(range(R.FACE_COUNT))
    runs = [{"rom": [(R.FACES, rom.data[R.FACES + 4 * n:R.FACES + 4 * n + 4] * R.FACE_COUNT)], "at": AT,
             "shot": True, "read": [("vram", R.FACE_VRAM, R.FACE_BYTES), ("cram", 0, 32)]} for n in faces]
    results = replay(args.rom, BOOT, runs)
    pal = rom.data[R.FACE_PALETTE:R.FACE_PALETTE + 32]
    bad, transparent = [], 0
    for n, res in zip(faces, results):
        vram, cram = res["read"]
        im = Image.open(res["shot"]).convert("RGB")
        px, rgb = rom.face_pixels(n), rom.face_rgb(n)
        screen = [i for i in range(40 * 48) if px[i] and im.getpixel((FACE_X + i % 40, FACE_Y + i // 40)) != rgb[i]]
        transparent += px.count(0)
        errs = [k for k, ok in (("vram", vram == rom.face_tiles(n)), ("cram", cram == pal),
                                ("screen", not screen)) if not ok]
        if errs:
            bad.append(f"face {n}: {', '.join(errs)}" + (f" ({len(screen)} pixels)" if screen else ""))
    print(f"faces {len(faces) - len(bad)}/{len(faces)}: VRAM, CRAM line 0 and screen match "
          f"({transparent} transparent colour-0 pixels skipped)")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
