#!/usr/bin/env python3
"""Verify the face decoding and the palette rules against the game.

1. Descriptor rules: start scenario 1 (verify_scenarios.boot) and, at the confirmation before the first turn,
   move the 4 players' head offices to cities of other areas (two runs cover all 7 areas); after the start
   ($9B34) each player's record +0x23 must be one of Rom.secretary_palettes(home), the secretary descriptor
   $FF22C4 + 4p = (0, image 0-6, that palette) and the 4 staff descriptors $FF1F84 + 16p kind 1 with distinct
   images 0-10.
2. Faces: save a state just before the secretary's first message; for each portrait of Rom.faces() write its
   (kind, image, palette) into player 1's secretary descriptor and record +0x23, and let the message draw it
   ($308E): VRAM (tile 0x2F0, or 0x6B0 for MAYOR) must hold the face's 960 bytes, the CRAM line the plane uses
   the palette, and the screen Rom.face_rgb pixel for pixel (colour 0 is transparent) in every cell that shows
   a face tile. SECRET / STAFF blink and talk: tiles of rows 2 and 4 (10-14, 20-24) then hold animation
   frames, which must come from the kind's animation data (the face itself or FACE_ANIM).

Usage: .venv/bin/python airmanage2/verify_faces.py [--rom ROM] [--faces 0,8,23]   # indices in Rom.faces() order
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
from verify_scenarios import GREETING, boot

PLANE_A = 0xC000                # 32 x 32 cells
MESSAGE = "c:10 w300"
# head offices per run: one home city of each area (player 1's first, players 2-4 after it)
HOMES = [(7, 9, 29, 12), (0, 19, 22, 8)]


def check_rules(rom: A.Rom) -> int:
    reads = [("ram", A.RAM_PLAYER, 4 * A.RAM_PLAYER_SIZE), ("ram", A.RAM_SECRETARY, 16), ("ram", A.RAM_STAFF, 64)]
    runs = [{"ram": [(A.RAM_PLAYER + A.RAM_PLAYER_SIZE * p + 1, bytes([h])) for p, h in enumerate(homes)],
             "steps": GREETING, "at": 2500, "read": reads} for homes in HOMES]
    bad = 0
    for homes, res in zip(HOMES, replay(rom.path, boot(0), runs)):
        players, secs, staff = res["read"]
        for p, h in enumerate(homes):
            pal = players[A.RAM_PLAYER_SIZE * p + 0x23]
            sec = secs[4 * p:4 * p + 4]
            st = [staff[16 * p + 4 * k:16 * p + 4 * k + 4] for k in range(4)]
            ok = (players[A.RAM_PLAYER_SIZE * p + 1] == h and pal in rom.secretary_palettes(h)
                  and sec[:2] == b"\0\0" and sec[2] < 7 and sec[3] == pal
                  and all(s[:2] == b"\0\1" and s[2] < 11 for s in st) and len({s[2] for s in st}) == 4)
            bad += not ok
            print(f"player {p + 1} home {h} ({rom.areas()[rom.city_area(h)]['name']}): palette {pal} "
                  f"(rule {rom.secretary_palettes(h)}), secretary image {sec[2]}, staff images {[s[2] for s in st]}"
                  + ("" if ok else "  NG"))
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼與調色盤規則的模擬器驗證")
    ap.add_argument("--rom", default=A.DEFAULT_ROM)
    ap.add_argument("--faces", help="只驗證這些頭像（Rom.faces() 的索引，逗號分隔）")
    args = ap.parse_args()
    rom = A.Rom(args.rom)
    bad_rules = check_rules(rom)

    faces = rom.faces()
    pick = [int(x) for x in args.faces.split(",")] if args.faces else list(range(len(faces)))
    runs = []
    for i in pick:
        f = faces[i]
        runs.append({"ram": [(A.RAM_SECRETARY, bytes([0, f["kind"], f["image"], f["palette"]])),
                             (A.RAM_PLAYER + 0x23, bytes([f["palette"]]))],
                     "steps": MESSAGE, "at": 250, "shot": True,
                     "read": [("vram", 0x6B0 * 32 if f["kind"] == 3 else 0x2F0 * 32, A.FACE_BYTES), ("cram", 0, 128),
                              ("vram", PLANE_A, 0x800)]})
    results = replay(rom.path, boot(0) + GREETING, runs)
    anim = rom.data[slice(*A.FACE_ANIM)]
    bad, anim_cells, shown = [], 0, 0
    for i, res in zip(pick, results):
        f = faces[i]
        vram, cram, plane = res["read"]
        im = Image.open(res["shot"]).convert("RGB")
        os.remove(res["shot"])
        raw = rom.face_raw(f["kind"], f["image"])
        base = 0x6B0 if f["kind"] == 3 else 0x2F0
        cells = {}
        for c in range(32 * 32):
            e = int.from_bytes(plane[2 * c:2 * c + 2], "big")
            if base <= (e & 0x7FF) < base + 30:
                cells[(e & 0x7FF) - base] = (c % 32, c // 32, e >> 13 & 3)
        lines = {v[2] for v in cells.values()}
        line = lines.pop() if len(lines) == 1 else None
        pal = b"".join(c.to_bytes(2, "big") for c in rom.face_palette(f["palette"]))
        rgb, idx = rom.face_rgb(f["kind"], f["image"], f["palette"]), rom.face_pixels(f["kind"], f["image"])
        screen_ok = anim_ok = True
        for t in range(30):
            got = vram[32 * t:32 * t + 32]
            if got != raw[32 * t:32 * t + 32]:
                anim_cells += 1
                anim_ok &= f["kind"] < 2 and t // A.FACE_W in (2, 4) and (got in anim or got in raw)
                continue
            if t not in cells:
                continue
            cx, cy, _ = cells[t]
            tx, ty = t % A.FACE_W * 8, t // A.FACE_W * 8
            screen_ok &= all(im.getpixel((8 * cx + x, 8 * cy + y)) == rgb[ty + y][tx + x]
                             for y in range(8) for x in range(8) if idx[ty + y][tx + x])
        shown += len(cells) == 30
        cram_ok = line is not None and cram[32 * line:32 * line + 32] == pal
        errs = [k for k, ok in (("plane", len(cells) == 30), ("cram", cram_ok), ("screen", screen_ok),
                                ("animation", anim_ok)) if not ok]
        if errs:
            bad.append(f"{i} {f['file']} {f['image']} palette {f['palette']}: {', '.join(errs)}")
    print(f"faces {len(pick) - len(bad)}/{len(pick)}: VRAM, CRAM and screen match ({anim_cells} animation tiles, "
          f"all from the animation data)")
    for b in bad:
        print("  " + b)
    sys.exit(1 if bad or bad_rules else 0)


if __name__ == "__main__":
    main()
