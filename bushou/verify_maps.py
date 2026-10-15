#!/usr/bin/env python3
"""Check the big map decode (rom.Rom.map_entries / map_tile / map_rgb) against the game (MAME, about 10 s), and
cross-check the battle map terrain with the SFC version.

1. Big map: on the daimyo selection map of scenario 1 the VDP is read back: plane B (nametable 0xE000, 32 x 128
   cells, vertical scroll 0x100 = 32 rows) must hold the ROM tilemap at cells (1 + c, 32 + r), VRAM tiles
   0x3FC.. the 429 ROM tiles, CRAM palette 0 the ROM palette. In the screenshot every map cell not covered by
   plane A (text, daimyo crests) or a sprite (cursor) must equal map.png (map_rgb) pixel for pixel; colour 0 shows the backdrop.
2. Battle maps: the MD has no screen for them before a battle (not reached here); their terrain bytes are compared
   with the SFC ROM (superfamicom-re/bushou, whose verify_maps.py checked the field maps against the SFC game).

Usage: .venv/bin/python bushou/verify_maps.py [--rom ROM] [--sfc SFC_ROM]
"""
import argparse
import os
import sys
import time
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import (
    CASTLE_COUNT,
    CASTLE_LAYER,
    CASTLE_MAPS,
    DEFAULT_ROM,
    FIELD_COUNT,
    FIELD_MAPS,
    MAP_CHR_COUNT,
    MAP_CHR_TILE,
    MAP_PALETTE,
    MAP_W,
    Rom,
    be16,
    decode_tile,
    md_rgb,
)

BOOT = ("w3500 start:10 w300 start:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w300 "
        "up:6 w60 c:10 w300")  # title -> scenario 1, 1 player -> daimyo selection map
PLANE, PLANE_W, B_ROW, B_COL = 0xE000, 32, 32, 1
SAT = 0xDC00
SFC_ROM = os.path.expanduser("~/works/superfamicom-re/roms/Super Nobunaga no Yabou - Bushou Fuuunroku (Japan).zip")
SFC = {"field": (0x3746A, 48 * 154), "castle": (0x393B2, 49 * 143), "castle layer": (0x3B0BE, 49 * 143)}


def load_sfc(path: str) -> bytes:
    with zipfile.ZipFile(path) as z:
        data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    return data[len(data) % 0x8000:]


def sprite_cells(vram: bytes) -> set[tuple[int, int]]:
    """Screen cells (column, row) touched by a sprite of the sprite table (the map cursor)."""
    out, k = set(), 0
    for _ in range(80):
        o = SAT + 8 * k
        y, size, link, x = (be16(vram, o) & 0x3FF) - 128, vram[o + 2], vram[o + 3] & 0x7F, (be16(vram, o + 6) & 0x1FF) - 128
        w, h = 8 * ((size >> 2 & 3) + 1), 8 * ((size & 3) + 1)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                out.add((xx // 8, yy // 8))
        if link == 0:
            break
        k = link
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖與戰場地形")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--sfc", default=SFC_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    res = replay(args.rom, BOOT, [{"at": 10, "shot": True, "read": [("vram", 0, 0x10000), ("cram", 0, 128)]}])[0]
    vram, cram = res["read"]
    errors = 0

    def cell(base: int, c: int, r: int) -> int:
        return be16(vram, base + 2 * (r * PLANE_W + c))

    entries = rom.map_entries()
    tm_ok = sum(cell(PLANE, B_COL + i % MAP_W, B_ROW + i // MAP_W) == e for i, e in enumerate(entries))
    chr_ok = sum(vram[32 * (MAP_CHR_TILE + k):32 * (MAP_CHR_TILE + k + 1)] == rom.map_tile(MAP_CHR_TILE + k)
                 for k in range(MAP_CHR_COUNT))
    pal_ok = cram[:32] == rom.data[MAP_PALETTE:MAP_PALETTE + 32]
    print(f"[tilemap] {tm_ok}/{len(entries)} plane B cells equal the ROM tilemap")
    print(f"[tiles] {chr_ok}/{MAP_CHR_COUNT} VRAM tiles equal the ROM; [palette] CRAM 0 {'OK' if pal_ok else 'NG'}")
    errors += (tm_ok != len(entries)) + (chr_ok != MAP_CHR_COUNT) + (not pal_ok)

    # screenshot, cells where plane A (row r, same column) draws nothing
    regs_bg = md_rgb(be16(cram, 0))  # backdrop; colour 0 of the map is transparent
    w, _, rgb = rom.map_rgb()
    im = Image.open(res["shot"]).convert("RGB")
    px = im.load()
    idx = []  # colour numbers of the map, to know which pixels are colour 0
    for i, e in enumerate(entries):
        idx.append(decode_tile(rom.map_tile(e & 0x7FF)))
    sprites = sprite_cells(vram)
    free = shown = 0
    for i, e in enumerate(entries):
        c, r = i % MAP_W, i // MAP_W
        a = cell(PLANE, B_COL + c, r)
        if any(decode_tile(vram[32 * (a & 0x7FF):32 * (a & 0x7FF) + 32])) or (B_COL + c, r) in sprites:
            continue
        free += 1
        ok = True
        for y in range(8):
            for x in range(8):
                want = rgb[(r * 8 + y) * w + c * 8 + x]
                k = (7 - y if e >> 12 & 1 else y) * 8 + (7 - x if e >> 11 & 1 else x)
                if idx[i][k] == 0:
                    want = regs_bg
                ok &= px[(B_COL + c) * 8 + x, r * 8 + y] == want
        shown += ok
    print(f"[screenshot] {shown}/{free} map cells not covered by plane A or sprites equal map.png (colour 0 = backdrop)")
    errors += shown != free

    if os.path.exists(args.sfc):
        sfc = load_sfc(args.sfc)
        for name, md_off, (sfc_off, size) in zip(SFC, (FIELD_MAPS, CASTLE_MAPS, CASTLE_LAYER), SFC.values()):
            same = rom.data[md_off:md_off + size] == sfc[sfc_off:sfc_off + size]
            print(f"[battle] {name}: MD 0x{md_off:05X} == SFC 0x{sfc_off:05X} ({size} bytes): {'OK' if same else 'NG'}")
            errors += not same
        print(f"  ({FIELD_COUNT} field maps 14x11, {CASTLE_COUNT} castle maps 13x11)")
    else:
        print("[battle] SFC ROM not found, skipped")
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
