#!/usr/bin/env python3
"""Verify the face decoding against the game: start scenario 3 as 日本軍 and open the 将校データ screen, where the
game draws the first admiral's face with $9E00 (tiles at VRAM $7800, palette CRAM line 3). For every face n (0-53)
the ROM is patched so that $9E00 draws face n (D2 = n instead of the admiral's index, and the random variants of
faces 0x2A / 0x2B / 0x31 / 0x32 switched off); then VRAM $7800 (30 tiles) must be rom.face_raw(n), CRAM line 3
rom.face_palette(n) and the 40x48 screen area rom.face_rgb(n) on every pixel of a colour other than 0 (colour 0 is
transparent and shows the backdrop).

Usage: .venv/bin/python teitoku/verify_faces.py [--faces 0,40,53]
"""
import argparse
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as T
from replay import replay
from verify_scenarios import TITLE

# scenario 3, 1 player, 日本軍 → situation, victory conditions → budget: B, Y/N … the next C opens 将校データ
BOOT = (TITLE + "down:10 w60 down:10 w60 c:20 w300 up:10 w60 c:20 w300 c:20 w300 c:20 w300 c:20 w600 "
        "c:20 w300 c:20 w300 c:20 w300 start:20 w300 c:20 w300 c:20 w300 b:20 w300")
FACE_X, FACE_Y = 32, 32           # plane cells (4, 4)-(8, 9)
VRAM_FACE, CRAM_LINE = 0x7800, 3
NO_RANDOM = [(0x9E32, b"\x00\xff"), (0x9E38, b"\x00\xff"), (0x9E5A, b"\x00\xff"), (0x9E60, b"\x00\xff")]


def patches(n: int) -> list[tuple[int, bytes]]:
    # 9E14: move.l A2,D0 / bne → move.l A2,D0 / nop; 9E18: move.w ($16,A6),D2 → moveq #n,D2 / nop
    return [(0x9E14, b"\x20\x0a\x4e\x71"), (0x9E18, bytes([0x74, n]) + b"\x4e\x71"), *NO_RANDOM]


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼的模擬器驗證")
    ap.add_argument("--faces", help="只驗證這些頭像號（逗號分隔）")
    args = ap.parse_args()
    rom = T.Rom()
    faces = [int(x) for x in args.faces.split(",")] if args.faces else list(range(T.FACE_COUNT))
    runs = [{"rom": patches(n), "steps": "c:20 w300", "at": 320, "shot": True,
             "read": [("vram", VRAM_FACE, T.FACE_BYTES), ("cram", 0, 128)]} for n in faces]
    bad, checked = [], 0
    for n, res in zip(faces, replay(rom.path, BOOT, runs)):
        vram, cram = res["read"]
        im = Image.open(res["shot"]).convert("RGB")
        os.remove(res["shot"])
        pal = b"".join(c.to_bytes(2, "big") for c in rom.face_palette(n))
        px, rgb = rom.face_pixels(n), rom.face_rgb(n)
        scr = [i for i in range(40 * 48) if px[i] and im.getpixel((FACE_X + i % 40, FACE_Y + i // 40)) != rgb[i]]
        checked += sum(1 for c in px if c)
        errs = [k for k, ok in (("vram", vram == rom.face_raw(n)), ("cram", cram[32 * CRAM_LINE:32 * CRAM_LINE + 32] == pal),
                                ("screen", not scr)) if not ok]
        if errs:
            bad.append(f"{n}: {', '.join(errs)}" + (f" ({len(scr)} px)" if scr else ""))
    print(f"faces {len(faces) - len(bad)}/{len(faces)}: VRAM, CRAM line {CRAM_LINE} and screen match "
          f"({checked} non-transparent pixels compared)")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
