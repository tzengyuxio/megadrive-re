#!/usr/bin/env python3
"""Verify the face decoding against the game: the prologue shows レオン with $8266(5, 6, code, 1), the code read
from the table at 0xD85AA ($FCA4). For every face code that read is patched to `move.l #code,-(a7)`, so the game's
own face routine draws it ($8068 for portraits, $AE36 for composite codes above 0xFFF). Compared: VRAM tile $200
(the 960 bytes = rom.face(code)), CRAM line 0 (= FACE_PALETTE) and the 40 x 48 screen area at (40, 40)
(= rom.face_rgb(code)).

Codes: the 53 portraits, the 20 admirals' composite codes and, per head and page, the code that takes that page
for every slot (16), so every part is drawn once.

Usage: .venv/bin/python daikoukai/verify_faces.py [--rom ROM] [--codes 0,0x13FF]
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

# power-on → title → new game → default name → spend the bonus → default ship name (the confirmation is next;
# the prologue's first face comes after two more C)
NEW_GAME = ("w900 start w500 start w300 c:10 w200 start:10 w200 c:10 w300 " + "c:10 w60 " * 8 +
            "down:10 w60 c:10 w60 c:10 w100 c:10 w300 start:10 w300")
CODE_READ, CODE_PUSHED = 0xFC9C, 0xFCB6     # moveq / move.b $ff43f6 / table lookup ... move.l d0,-(a7)
SCREEN_X, SCREEN_Y = 40, 40


def patch(code: int) -> bytes:
    return bytes.fromhex(f"2F3C{code:08X}60{CODE_PUSHED - (CODE_READ + 8):02X}")   # move.l #code,-(a7); bra.s


def codes(rom: R.Rom) -> list[int]:
    admirals = sorted({p["face"] for p in rom.persons() if R.is_composite(p["face"])})
    cover = [0x1000 | h << 10 | p << 8 | p << 6 | p << 4 | p << 2 | p for h in range(4) for p in range(4)]
    return list(range(R.PORTRAIT_COUNT)) + admirals + [c for c in cover if c not in admirals]


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--codes", help="只驗證這些頭像碼（逗號分隔，可 0x）")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    todo = [int(x, 0) for x in args.codes.split(",")] if args.codes else codes(rom)
    runs = [{"rom": [(CODE_READ, patch(c))], "steps": "c:10 w300 c:10 w200", "at": 560, "shot": True,
             "read": [("vram", 0x200 * 32, R.FACE_BYTES), ("cram", 0, 32)]} for c in todo]
    results = replay(args.rom, NEW_GAME, runs)
    pal = b"".join(w.to_bytes(2, "big") for w in rom.face_palette())
    bad = []
    for c, res in zip(todo, results):
        vram, cram = res["read"]
        im = Image.open(res["shot"]).convert("RGB")
        screen = [im.getpixel((SCREEN_X + i % 40, SCREEN_Y + i // 40)) for i in range(40 * 48)]
        os.remove(res["shot"])
        errs = [k for k, ok in (("vram", vram == rom.face(c)), ("cram", cram == pal),
                                ("screen", screen == rom.face_rgb(c))) if not ok]
        if errs:
            bad.append(f"{c:04X}: {', '.join(errs)}")
    n_portrait = sum(not R.is_composite(c) for c in todo)
    print(f"faces {len(todo) - len(bad)}/{len(todo)} (portraits {n_portrait}, composite {len(todo) - n_portrait}): "
          "VRAM, CRAM line 0 and screen match")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
