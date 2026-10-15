#!/usr/bin/env python3
"""Verify the portrait decoding against the game: start scenario 2 as 織田信長 in MAME and, for every portrait n
(0-72), write n into the person id of 織田's daimyo record (slot 24) before the ability screen opens. The screen
must then show rom.face_pixels(n): VRAM $4000 (30 tiles) = the decompressed stream, CRAM line 2 = FACE_PALETTE
and the 40x48 screen area = rom.face_rgb(n), pixel by pixel. The USA version takes the same key presses.

Usage: .venv/bin/python zenkoku/verify_faces.py [--rom ROM] [--faces 0,31,72]   # Japan (default) or USA ROM
"""
import argparse
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as Z
from replay import replay

# power-on → title (A skips the intro, START twice) → new game → scenario 2 → no CPU war, no dialect, 1 player →
# 尾張 → 織田信長 Yes → the 姓名を変更しますか question
TITLE = "w700 a:10 w1900 start:10 w60 start:10 w60 start:10 w200 "
SCENARIO2 = TITLE + "c:10 w200 down:6 w30 c:10 w600 b:10 w200 b:10 w200 up:6 w30 c:10 w300 c:10 w300 c:10 w300"
SLOT = 24  # 織田信長 in scenarios 2-4 (尾張 = province 24)
FACE_X, FACE_Y = 152, 32  # plane A cells (19, 4)-(23, 9)


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼的模擬器驗證")
    ap.add_argument("--rom", default=Z.DEFAULT_ROM)
    ap.add_argument("--faces", help="只驗證這些頭像號（逗號分隔）")
    args = ap.parse_args()
    rom = Z.Rom(args.rom)
    faces = [int(x) for x in args.faces.split(",")] if args.faces else list(range(Z.PORTRAIT_COUNT))
    person = 0xFF0000 + Z.DAIMYO_RAM + Z.DAIMYO_SIZE * SLOT + 6
    runs = [{"ram": [(person, n.to_bytes(2, "big"))], "steps": "b:10 w300", "at": 300, "shot": True,
             "read": [("vram", 0x4000, Z.FACE_BYTES), ("cram", 0, 128)]} for n in faces]
    results = replay(args.rom, SCENARIO2, runs)
    pal = b"".join(rom.u16(rom.L.face_palette + 2 * i).to_bytes(2, "big") for i in range(16))
    bad = []
    for n, res in zip(faces, results):
        vram, cram = res["read"]
        im = Image.open(res["shot"]).convert("RGB")
        screen = [im.getpixel((FACE_X + i % 40, FACE_Y + i // 40)) for i in range(40 * 48)]
        os.remove(res["shot"])
        errs = [k for k, ok in (("vram", vram == rom.face_raw(n)), ("cram", cram[64:96] == pal),
                                ("screen", screen == rom.face_rgb(n))) if not ok]
        if errs:
            bad.append(f"{n}: {', '.join(errs)}")
    print(f"portraits {len(faces) - len(bad)}/{len(faces)}: VRAM, palette and screen match")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
