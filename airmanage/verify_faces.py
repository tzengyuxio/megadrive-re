#!/usr/bin/env python3
"""Verify the face decoding and palette pairing against the game. Start scenario 1 (verify_scenarios.boot) and
save a state on the main screen; check that the descriptors the game made for the 4 players' aides
(RAM_MANAGER) and negotiation partners (RAM_PERSON) use the palettes Rom.default_palette gives; then, for each of
the 33 faces, write (kind, image, default palette) into player 1's aide descriptor and open the 航路 menu
(right, right, C), which draws the aide: VRAM 0x2A20 (tiles 0x151-0x16E) must be the face's 960 bytes, CRAM
line 3 the palette, and the screen Rom.face_rgb pixel by pixel (colour 0 is transparent) in every cell that shows
a face tile. The game
puts the eye / mouth animation over a few cells (plane A cells pointing at tiles 0x16F-0x174, loaded from the
kind's EYE / MOUTH files); those tiles are checked to come from the kind's animation files.

Usage: .venv/bin/python airmanage/verify_faces.py [--rom ROM] [--faces 0,8,28]   # indices in Rom.faces() order
"""
import argparse
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as A
from replay import replay
from verify_scenarios import boot

ROUTE_MENU = "right:10 w40 right:10 w40 c:10 w200"
FACE_VRAM = 0x2A20
FACE_TILE = 0x151
ANIM_TILES = 6  # 0x16F-0x174
PLANE_A = 0xC000
# eye / mouth animation tiles per kind (ROM ranges holding the EYE / MOUTH files; MANAGER image 7's tiles follow
# each of its two files, outside their size fields)
ANIM_RANGES = [(0x7112A, 0x7232E), (0x7232E, 0x75032), (0x75032, 0x755D4)]
FACE_X, FACE_Y = 200, 152  # screen position of the aide in the 航路 menu


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼與調色盤配對的模擬器驗證")
    ap.add_argument("--rom", default=A.DEFAULT_ROM)
    ap.add_argument("--faces", help="只驗證這些頭像（Rom.faces() 的索引，逗號分隔）")
    args = ap.parse_args()
    rom = A.Rom(args.rom)
    faces = rom.faces()
    pick = [int(x) for x in args.faces.split(",")] if args.faces else list(range(len(faces)))
    runs = [{"steps": "w10", "at": 20, "read": [("ram", A.RAM_PERSON, 48), ("ram", A.RAM_MANAGER, 16)]}]
    runs += [{"ram": [(A.RAM_MANAGER, bytes([0, faces[i]["kind"], faces[i]["image"], faces[i]["palette"]]))],
              "steps": ROUTE_MENU, "at": 400, "shot": True,
              "read": [("vram", FACE_VRAM, A.FACE_BYTES + 32 * ANIM_TILES), ("cram", 0, 128),
                       ("vram", PLANE_A, 0x800)]} for i in pick]
    results = replay(args.rom, boot(0), runs)

    persons, managers = results[0]["read"]
    descs = [(1, persons[4 * k + 2], persons[4 * k + 3]) for k in range(12)]
    descs += [(0, managers[4 * k + 2], managers[4 * k + 3]) for k in range(4)]
    kinds_ok = all(persons[4 * k:4 * k + 2] == b"\0\1" for k in range(12)) and \
        all(managers[4 * k:4 * k + 2] == b"\0\0" for k in range(4))
    pair_bad = [d for d in descs if rom.default_palette(d[0], d[1]) != d[2]]
    print(f"game descriptors: aides {[d[1:] for d in descs[12:]]}, partners {[d[1:] for d in descs[:12]]}: "
          f"palettes as Rom.default_palette {len(descs) - len(pair_bad)}/{len(descs)}" + ("" if kinds_ok else ", kind NG"))

    bad, anim_cells = [], 0
    for i, res in zip(pick, results[1:]):
        f = faces[i]
        vram, cram, plane = res["read"]
        pal = b"".join(c.to_bytes(2, "big") for c in rom.face_palette(f["palette"]))
        im = Image.open(res["shot"]).convert("RGB")
        os.remove(res["shot"])
        rgb = rom.face_rgb(f["kind"], f["image"])
        idx = rom.face_pixels(f["kind"], f["image"])
        anim = rom.data[slice(*ANIM_RANGES[f["kind"]])]
        screen_ok = anim_ok = True
        for cell in range(A.FACE_W * A.FACE_H):
            cx, cy = cell % A.FACE_W, cell // A.FACE_W
            e = plane[2 * ((FACE_Y // 8 + cy) * 32 + FACE_X // 8 + cx):][:2]
            tile = int.from_bytes(e, "big") & 0x7FF
            if tile == FACE_TILE + cell:
                # colour 0 is transparent on screen
                screen_ok &= all(im.getpixel((FACE_X + 8 * cx + x, FACE_Y + 8 * cy + y)) == rgb[8 * cy + y][8 * cx + x]
                                 for y in range(8) for x in range(8) if idx[8 * cy + y][8 * cx + x])
            else:
                anim_cells += 1
                k = tile - FACE_TILE - A.FACE_W * A.FACE_H
                t = vram[A.FACE_BYTES + 32 * k:A.FACE_BYTES + 32 * k + 32] if 0 <= k < ANIM_TILES else None
                anim_ok &= t is not None and t in anim
        errs = [k for k, ok in (("vram", vram[:A.FACE_BYTES] == rom.face_raw(f["kind"], f["image"])),
                                ("cram", cram[96:128] == pal), ("screen", screen_ok), ("animation", anim_ok)) if not ok]
        if errs:
            bad.append(f"{f['file']} {f['image']}: {', '.join(errs)}")
    print(f"faces {len(pick) - len(bad)}/{len(pick)}: VRAM, CRAM line 3 and screen match "
          f"({anim_cells} animation cells, their tiles from the EYE / MOUTH files)")
    for b in bad:
        print("  " + b)
    sys.exit(1 if bad or pair_bad or not kinds_ok else 0)


if __name__ == "__main__":
    main()
