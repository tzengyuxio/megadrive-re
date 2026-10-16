#!/usr/bin/env python3
"""Verify the face decoding against the game: on the "Select side." screen the game draws George Washington's face
(person 238) with $EE6A into VRAM $D080 (30 tiles, palette CRAM line 2) at screen (64, 88). For every face code the
ROM is patched so that person 238 has that code; then VRAM $D080 must be rom.face_raw(code), CRAM line 2
rom.face_palette() and the 40x48 screen area rom.face_rgb(code) on every pixel of a colour other than 0 (colour 0 is
transparent and shows the backdrop).

Codes: the 174 portraits, every composite code a person uses, and per type the 4 codes whose 5 part digits are all
the same (together they draw every variant of every part).

Usage: .venv/bin/python dokuritsu/verify_faces.py [--quick] [--codes 75,8766]   # hex codes
"""
import argparse
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as L
from replay import replay

# power-on → title (START) → Start New Game → "Select game set-up." (the next C opens "Select side.")
TITLE = "w1600 start:10 w200 start:10 w300 "
BOOT = TITLE + "c:20 w300"
WASHINGTON = 238
FACE_X, FACE_Y = 64, 88
VRAM_FACE, CRAM_LINE = 0xD080, 2


def all_codes(rom: L.Rom, quick: bool) -> list[int]:
    used = sorted({p["face"] for p in rom.persons() if p["face"] & 0x8000})
    synthetic = [0x8000 | t << 10 | v * 0x155 for t in range(L.TYPE_COUNT) for v in range(4)]
    portraits = list(range(L.PORTRAIT_COUNT))
    if quick:
        return portraits[::17] + used[::25] + synthetic[::5]
    return portraits + used + [c for c in synthetic if c not in used]


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼的模擬器驗證")
    ap.add_argument("--quick", action="store_true", help="只抽樣")
    ap.add_argument("--codes", help="只驗證這些頭像碼（十六進位，逗號分隔）")
    args = ap.parse_args()
    rom = L.Rom()
    codes = [int(x, 16) for x in args.codes.split(",")] if args.codes else all_codes(rom, args.quick)
    face_at = L.PERSONS + L.PERSON_SIZE * WASHINGTON + 34
    runs = [{"rom": [(face_at, c.to_bytes(2, "big"))], "steps": "c:20 w300", "at": 340, "shot": True,
             "read": [("vram", VRAM_FACE, L.FACE_BYTES), ("cram", 0, 128)]} for c in codes]
    pal = b"".join(c.to_bytes(2, "big") for c in rom.face_palette())
    bad, checked = [], 0
    for c, res in zip(codes, replay(rom.path, BOOT, runs)):
        vram, cram = res["read"]
        im = Image.open(res["shot"]).convert("RGB")
        os.remove(res["shot"])
        px, rgb = rom.face_pixels(c), rom.face_rgb(c)
        scr = [i for i in range(40 * 48) if px[i] and im.getpixel((FACE_X + i % 40, FACE_Y + i // 40)) != rgb[i]]
        checked += sum(1 for v in px if v)
        errs = [k for k, ok in (("vram", vram == rom.face_raw(c)), ("cram", cram[32 * CRAM_LINE:32 * CRAM_LINE + 32] == pal),
                                ("screen", not scr)) if not ok]
        if errs:
            bad.append(f"{c:04X}: {', '.join(errs)}" + (f" ({len(scr)} px)" if scr else ""))
    portraits = sum(1 for c in codes if not c & 0x8000)
    print(f"faces {len(codes) - len(bad)}/{len(codes)} (portraits {portraits}, composite {len(codes) - portraits}): "
          f"VRAM, CRAM line {CRAM_LINE} and screen match ({checked} non-transparent pixels compared)")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
