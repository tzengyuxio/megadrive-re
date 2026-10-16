#!/usr/bin/env python3
"""Verify the face decoding against the game: a new game with type 1 (木下藤吉郎) opens with an event on the 尾張
map that shows 藤吉郎's face (name 0, face code 0) through $E36E: VRAM tile 0x260, palette line 0, plane A cell
(21, 13) = screen (168, 104). Every run starts from a savestate taken at the last button press before the event
and patches the face code of name 0 (ROM NAME_FACE0, read by $17642 when the event starts) to the face to test.
Then compares VRAM (640 bytes at tile 0x260) with rom.face_raw, CRAM line 0 with FACE_PALETTE and the 32x40
screen area with rom.face_rgb, pixel by pixel. Colour 0 is transparent on the MD (the plane behind shows), so its
pixels are left out of the screen comparison.
Faces tested: the 258 portraits and every composite code of the name table (518).

Usage: .venv/bin/python taikou/verify_faces.py [--rom ROM] [--quick]
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

# title → 新たな物語を始める → type 1 → よろしい → spend the 50 points → confirm → the opening event
NEW_GAME = ("w1500 start:10 w200 start:10 w200 c:10 w300 c:10 w300 c:10 w300 c:900 w100 "
            "a:10 w300 start:10 w300 c:10 w300 c:10 w300 c:10")
AT = 530                              # frames after the savestate: the face is on screen
NAME_FACE0 = R.NAMES + 14             # face code of name 0
FACE_X, FACE_Y = 21 * 8, 13 * 8


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="只驗證頭像 0、1、257 與 3 個組合臉")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    comps = sorted({n["face"] for n in rom.names() if R.is_composite(n["face"])})
    codes = list(range(R.PORTRAIT_COUNT)) + comps
    if args.quick:
        codes = [0, 1, R.PORTRAIT_COUNT - 1] + comps[::len(comps) // 2][:3]
    runs = [{"rom": [(NAME_FACE0, c.to_bytes(2, "big"))], "at": AT, "shot": True,
             "read": [("vram", R.FACE_VRAM_TILE * 32, R.FACE_BYTES), ("cram", 0, 32)]} for c in codes]
    results = replay(args.rom, NEW_GAME, runs)
    pal = rom.data[R.FACE_PALETTE:R.FACE_PALETTE + 32]
    bad, transparent = [], 0
    for c, res in zip(codes, results):
        vram, cram = res["read"]
        im = Image.open(res["shot"]).convert("RGB")
        px, rgb = rom.face_pixels(c), rom.face_rgb(c)
        w = R.FACE_W * 8
        screen = [i for i in range(len(px)) if px[i] and im.getpixel((FACE_X + i % w, FACE_Y + i // w)) != rgb[i]]
        transparent += px.count(0)
        errs = [k for k, ok in (("vram", vram == rom.face_raw(c)), ("cram", cram == pal), ("screen", not screen))
                if not ok]
        if errs:
            bad.append(f"code {c:04X}: {', '.join(errs)}")
    n_pt = sum(1 for c in codes if not R.is_composite(c))
    print(f"faces {len(codes) - len(bad)}/{len(codes)} (portraits {n_pt}, composite codes {len(codes) - n_pt}): "
          f"VRAM, CRAM line 0 and screen match ({transparent} transparent colour-0 pixels skipped)")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
