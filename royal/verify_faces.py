#!/usr/bin/env python3
"""Verify the portrait decoding against the game: scenario 1, 1 player, house selection screen (the cursor is on
the first house; the screen shows the person SELECT_HEADS[0] = 4 エラン, whose face $62B0 → $6244 draws at VRAM
tile $300, CRAM line 3, screen (24, 112)). Every run starts from a savestate on the 何人でプレイしますか menu and
- persons 0-63: patches SELECT_HEADS[0] to n, so the game takes person n's record ($4E58) and its face number
  from the record address ($4E6A);
- advisers 64-67 and the 23 unit faces: patches the face table address in $6244 (the long at FACE_BASE_PATCH) so
  that face 4 (エラン) is read from the adviser / unit face instead.
Then compares VRAM ($6000, 960 bytes) with rom.face_raw, CRAM line 3 with FACE_PALETTE and the 40x48 screen area
with rom.face_rgb, pixel by pixel. Colour 0 is transparent on the MD, so pixels of colour 0 (3 pixels of person 15
only) show the plane behind the face and are left out of the screen comparison.

Usage: .venv/bin/python royal/verify_faces.py [--rom ROM] [--quick]
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
from verify_scenarios import TITLE

PLAYERS_MENU = TITLE + "w100 c:4 w220 c:4 w220"  # scenario 1 → its story → 何人でプレイしますか
SHOWN = 4                                        # エラン, the head in scenario 1
FACE_BASE_PATCH = 0x625E                         # addi.l #$40000, D0 in $6244
FACE_X, FACE_Y = 24, 112


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="只驗證人物 0、4、63，相談役 64，部隊 0、22")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    assert rom.data[FACE_BASE_PATCH - 2:FACE_BASE_PATCH + 4] == bytes.fromhex("068000040000")
    faces = [("person", n) for n in range(R.ADVISER_FIRST)] + [("adviser", n) for n in range(64, 68)]
    faces += [("unit", n) for n in range(R.UNIT_COUNT)]
    if args.quick:
        faces = [f for f in faces if f in {("person", 0), ("person", 4), ("person", 63), ("adviser", 64),
                                           ("unit", 0), ("unit", 22)}]
    runs = []
    for kind, n in faces:
        run = {"steps": "c:4 w220", "at": 240, "shot": True,
               "read": [("vram", 0x6000, R.FACE_BYTES), ("cram", 0, 128)]}
        if kind == "person":
            run["rom"] = [(R.SELECT_HEADS, bytes([n]))]
        else:
            base = (R.UNIT_FACES_ROM if kind == "unit" else R.FACES_ROM) + R.FACE_BYTES * (n - SHOWN)
            run["rom"] = [(FACE_BASE_PATCH, base.to_bytes(4, "big"))]
        runs.append(run)
    results = replay(args.rom, PLAYERS_MENU, runs)
    pal = rom.data[R.FACE_PALETTE:R.FACE_PALETTE + 32]
    bad, transparent = [], 0
    for (kind, n), res in zip(faces, results):
        vram, cram = res["read"]
        unit = kind == "unit"
        im = Image.open(res["shot"]).convert("RGB")
        px, rgb = rom.face_pixels(n, unit), rom.face_rgb(n, unit)
        screen = [i for i in range(40 * 48) if px[i] and im.getpixel((FACE_X + i % 40, FACE_Y + i // 40)) != rgb[i]]
        transparent += px.count(0)
        errs = [k for k, ok in (("vram", vram == rom.face_raw(n, unit)), ("cram", cram[96:128] == pal),
                                ("screen", not screen)) if not ok]
        if errs:
            bad.append(f"{kind} {n}: {', '.join(errs)}")
    counts = {k: sum(1 for f in faces if f[0] == k) for k in ("person", "adviser", "unit")}
    print(f"faces {len(faces) - len(bad)}/{len(faces)} (persons {counts['person']}, advisers {counts['adviser']}, "
          f"units {counts['unit']}): VRAM, CRAM line 3 and screen match "
          f"({transparent} transparent colour-0 pixels skipped)")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
