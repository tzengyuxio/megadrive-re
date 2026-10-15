#!/usr/bin/env python3
"""Verify the portraits and the abilities against the game: in scenario 4 on the ruler-select map, write person n
into the ruler of 曹操's force ($FFE91C + 2) and open the ruler panel of 許昌 (A). The panel must show
rom.face_pixels(n) - VRAM tiles $4E2-$4FF (plane A cells (3,3)-(7,8)) = rom.face_raw(n), CRAM line 0 =
FACE_PALETTE and the 40x48 screen area = rom.face_rgb(n), pixel by pixel - and n's 武力 智力 政治 魅力 (digit d =
tile $7E0 + 2d, rows 3/6/9/12, last digit in column 20) = rom.abilities(3, n), base + item bonus. Portraits
500-535 have no person record: for them the portrait routine's `cmpi.w #$18F,D1` ($395E6) is patched to
`move.w #n,D1` (the following bls is then not taken, as for n >= 400) and only the picture is checked.

Usage: .venv/bin/python sgz5/verify_faces.py [--faces 0,285,535]
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
from verify_text import TO_MAP

PANEL_CITY, FORCE, SCENARIO = 18, 1, 3  # 許昌, 曹操's force, 201年 (the menu's default)
FACE_TILE, FACE_X, FACE_Y = 0x4E2, 24, 24
FACE_PATCH = 0x395E6
PLANE_A, WIDTH = 0xE000, 64
ABILITY_ROWS, ABILITY_COL = (3, 6, 9, 12), 20


def number_at(nt: bytes, row: int, col: int) -> int | None:
    digits = ""
    while col >= 0:
        t = (nt[(row * WIDTH + col) * 2] << 8 | nt[(row * WIDTH + col) * 2 + 1]) & 0x7FF
        if not (0x7E0 <= t <= 0x7F2 and t % 2 == 0):
            break
        digits = str((t - 0x7E0) // 2) + digits
        col -= 1
    return int(digits) if digits else None


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像與能力值的模擬器驗證（選君主畫面的君主資訊）")
    ap.add_argument("--faces", help="只驗證這些頭像號（逗號分隔）")
    args = ap.parse_args()
    rom = R.Rom()
    faces = [int(x) for x in args.faces.split(",")] if args.faces else list(range(R.FACE_COUNT))
    v = rom.u16(R.MAP_NODES + 2 * PANEL_CITY)
    cursor = (0xFF606C, (((v >> 8) + 16) * 8).to_bytes(2, "big") + (((v & 0xFF) + 17) * 8).to_bytes(2, "big"))
    runs = [{"ram": [cursor] + ([(0xFF0000 + R.RULERS_RAM + 2 * FORCE, n.to_bytes(2, "big"))]
                                if n < R.PERSON_COUNT else []),
             "rom": [(FACE_PATCH, bytes.fromhex("323C") + n.to_bytes(2, "big"))] if n >= R.PERSON_COUNT else [],
             "steps": "right:6 w40 a:10 w60", "at": 126, "shot": True,
             "read": [("vram", 32 * FACE_TILE, R.FACE_BYTES), ("cram", 0, 32), ("vram", PLANE_A, 14 * WIDTH * 2)]}
            for n in faces]
    results = replay(R.DEFAULT_ROM, TO_MAP, runs)
    pal = rom.d[R.FACE_PALETTE:R.FACE_PALETTE + 32]
    bad, abil_ok, abil_n = [], 0, 0
    for n, res in zip(faces, results):
        tiles, cram, nt = res["read"]
        im = Image.open(res["shot"]).convert("RGB")
        screen = [im.getpixel((FACE_X + i % R.FACE_W, FACE_Y + i // R.FACE_W)) for i in range(R.FACE_W * R.FACE_H)]
        os.remove(res["shot"])
        errs = [k for k, ok in (("vram", tiles == rom.face_raw(n)), ("cram", cram == pal),
                                ("screen", screen == rom.face_rgb(n))) if not ok]
        if n < R.PERSON_COUNT:
            abil_n += 1
            got = [number_at(nt, r, ABILITY_COL) for r in ABILITY_ROWS]
            if got == rom.abilities(SCENARIO, n):
                abil_ok += 1
            else:
                errs.append(f"abilities {got} (ROM {rom.abilities(SCENARIO, n)})")
        if errs:
            bad.append(f"{n}: {', '.join(errs)}")
    print(f"portraits {len(faces) - sum(('vram' in b or 'cram' in b or 'screen' in b) for b in bad)}/{len(faces)}: "
          f"VRAM, palette and screen match; abilities {abil_ok}/{abil_n} persons x 4 numbers read back")
    for b in bad[:20]:
        print("  NG " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
