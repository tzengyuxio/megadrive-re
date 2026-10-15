#!/usr/bin/env python3
"""Verify the string tables and the font against the game: on the ruler-select map, moving the cursor onto a city
makes the game draw the city name ($24A2, tiles $500-$507) and its ruler's name ($859A, tiles $508-$517) into VRAM,
one 16x16 glyph per 2x2 tiles (TL TR / BL BR). For every name n (0-502) the person lookup is patched to
`move.w #n,D1` ($85B4) and for every city k the city lookup to `move.w #k,D1; nop` ($24AE); the glyphs read back
from VRAM must equal rom.string_codes' glyphs from the ROM font.

Usage: .venv/bin/python sgz5/verify_text.py [--names 0,285,502]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from replay import replay

TO_MAP = "w900 start:10 w300 a:10 w300 a:10 w300"  # title → 開始遊戲 → scenario 4 → ruler-select map
HOVER_CITY = 8  # 濮陽 (曹操's); the cursor is put one step left of it and moved right
PERSON_PATCH, CITY_PATCH = 0x85B4, 0x24AE
CITY_TILE, PERSON_TILE = 0x500, 0x508


def vram_glyph(vram: bytes, t0: int) -> bytes:
    """The 32-byte font glyph (TL TR BL BR quadrants, 1 bit per pixel) drawn in tiles t0..t0+3."""
    out = bytearray()
    for t in range(t0, t0 + 4):
        for y in range(8):
            row = vram[32 * (t - CITY_TILE) + 4 * y:][:4]
            out.append(sum(1 << (7 - x) for x in range(8) if (row[x // 2] >> (4 if x % 2 == 0 else 0)) & 15))
    return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="字串表與字型的模擬器驗證（選君主畫面的城名／君主名）")
    ap.add_argument("--names", help="只驗證這些人名號（逗號分隔）")
    args = ap.parse_args()
    rom = R.Rom()
    names = [int(x) for x in args.names.split(",")] if args.names else list(range(R.NAME_COUNT))
    cities = [] if args.names else list(range(R.CITY_COUNT))
    x, y = rom.u16(R.MAP_NODES + 2 * HOVER_CITY) >> 8, rom.u16(R.MAP_NODES + 2 * HOVER_CITY) & 0xFF
    cursor = [(0xFF606C, ((x + 16) * 8).to_bytes(2, "big") + ((y + 17) * 8).to_bytes(2, "big"))]
    read = [("vram", 32 * CITY_TILE, 32 * 24)]
    runs = ([{"rom": [(PERSON_PATCH, bytes.fromhex("323C") + n.to_bytes(2, "big"))], "ram": cursor,
              "steps": "right:6 w40", "at": 66, "read": read} for n in names]
            + [{"rom": [(CITY_PATCH, bytes.fromhex("323C") + k.to_bytes(2, "big") + bytes.fromhex("4E71"))],
                "ram": cursor, "steps": "right:6 w40", "at": 66, "read": read} for k in cities])
    results = replay(R.DEFAULT_ROM, TO_MAP, runs)
    bad = []
    for i, res in enumerate(results):
        vram = res["read"][0]
        if i < len(names):
            label, codes, t0 = f"name {names[i]}", rom.string_codes(R.TABLES["names"], names[i]), PERSON_TILE
        else:
            k = cities[i - len(names)]
            label, codes, t0 = f"city {k}", rom.string_codes(R.TABLES["cities"], k), CITY_TILE
        got = [vram_glyph(vram, t0 + 4 * j) for j in range(len(codes))]
        if got != [rom.glyph(b, g) for b, g in codes]:
            bad.append(f"{label} {rom.text(codes)}")
    print(f"names {len(names) - sum(b.startswith('name') for b in bad)}/{len(names)}, "
          f"cities {len(cities) - sum(b.startswith('city') for b in bad)}/{len(cities)}: VRAM glyphs = ROM font")
    for b in bad[:20]:
        print("  NG " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
