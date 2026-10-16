#!/usr/bin/env python3
"""Verify the world map decoding against the game: start scenario 3 (1 player, 日本軍) and stop on the situation
screen (「日本の情勢」), which shows the world map on plane B under the text. VRAM tiles WORLD_TILE0.. must be the
ROM tiles, a 32 x 16 block of plane B the ROM tilemap, CRAM line 2 the palette, and the screen rom.world_rgb on
every map pixel of a colour other than 0 where plane A has no text.

Usage: .venv/bin/python teitoku/verify_maps.py
"""
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as T
from drive import events_lua, schedule
from mame import run
from verify_scenarios import scenario_steps

PLANE, PLANE_W = 0xE000, 64     # planes A and B share the 64 x 64 name table; B is scrolled down by 256 lines


def main() -> None:
    rom = T.Rom()
    events, end = schedule(scenario_steps(3).split())
    with tempfile.TemporaryDirectory() as tmp:
        run(rom.path, events_lua(events, f"{tmp}/s", end, False))
        vram, cram = Path(f"{tmp}/s.vram").read_bytes(), Path(f"{tmp}/s.cram").read_bytes()
        vsram = Path(f"{tmp}/s.vsram").read_bytes()
        im = Image.open(f"{tmp}/s.png").convert("RGB")
    t0 = 32 * T.WORLD_TILE0
    tiles_ok = vram[t0:t0 + 32 * T.WORLD_TILE_COUNT] == rom.data[T.WORLD_TILES:T.WORLD_TILES + 32 * T.WORLD_TILE_COUNT]
    words = [int.from_bytes(vram[PLANE + 2 * i:PLANE + 2 * i + 2], "big") for i in range(PLANE_W * 64)]
    tm = rom.world_tilemap()
    at = [(r, c) for r in range(64 - T.WORLD_H) for c in range(PLANE_W - T.WORLD_W + 1)
          if all(words[(r + y) * PLANE_W + c:(r + y) * PLANE_W + c + T.WORLD_W] == tm[y * T.WORLD_W:(y + 1) * T.WORLD_W]
                 for y in range(T.WORLD_H))]
    pal = bytes(rom.data[T.WORLD_PALETTE:T.WORLD_PALETTE + 32])
    cram_ok = cram[64:96] == pal
    print(f"tiles {T.WORLD_TILE_COUNT} at VRAM ${t0:04X}: {'OK' if tiles_ok else 'NG'}; "
          f"tilemap on plane B row/col {at[0] if at else 'not found'}; CRAM line 2: {'OK' if cram_ok else 'NG'}")
    bad = checked = 0
    if at:
        row, col = at[0]
        vs_b = int.from_bytes(vsram[2:4], "big")
        rgb, w = rom.world_rgb(), T.WORLD_W * 8
        idx = [[0] * w for _ in range(T.WORLD_H * 8)]   # colour index of each map pixel
        for i, e in enumerate(tm):
            raw = rom.data[T.WORLD_TILES + 32 * ((e & 0x7FF) - T.WORLD_TILE0):][:32]
            for k, c in enumerate(T.packed_pixels(raw, 1, 1)):
                idx[i // T.WORLD_W * 8 + k // 8][i % T.WORLD_W * 8 + k % 8] = c
        for y in range(T.WORLD_H * 8):
            sy = (row * 8 + y - vs_b) % 512
            if not 0 <= sy < im.height:
                continue
            for x in range(w):
                sx = col * 8 + x
                if sx >= im.width or idx[y][x] == 0 or words[(sy // 8) * PLANE_W + sx // 8]:
                    continue
                checked += 1
                bad += im.getpixel((sx, sy)) != rgb[y * w + x]
    print(f"screen: {checked - bad}/{checked} map pixels match")
    ok = tiles_ok and cram_ok and at and checked and not bad
    print("ALL OK" if ok else "NG")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
