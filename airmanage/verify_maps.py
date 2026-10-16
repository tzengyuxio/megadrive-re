#!/usr/bin/env python3
"""Verify the world map decoding against the game. On the HQ-selection screen (verify_scenarios.SCENARIO_SELECT +
HQ_SELECT) and on the main screen (verify_scenarios.boot(0)): VRAM tiles 0x180-0x37F must be the map file's 512
tiles, CRAM line 1 its palette and plane B (0xE000, 32 cells wide) rows MAP_ROW / 4 the tilemap + 0x180 (on the
HQ screen the frame covers the top map rows, so only the visible entries are counted; colours 3 and 4 flash on
the main screen and are left out). On the HQ screen the 22 city-marker sprites (sprite table 0xF000, entries
2-23, tile 0x753) must sit at the cities' CITY_XY (x, y + 24).

Usage: .venv/bin/python airmanage/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as A
from replay import replay
from verify_scenarios import HQ_SELECT, SCENARIO_SELECT, boot

PLANE_B, SPRITES = 0xE000, 0xF000
PLANE_W = 32
MARKER_TILE = 0x753
MAIN_ROW = 4
MAIN_WAIT = 300  # boot(0) ends on the 勝利条件 message; the map screen follows
FLASHING = (3, 4)  # main-screen CRAM line 1 colours that cycle


def main() -> None:
    ap = argparse.ArgumentParser(description="大地圖的模擬器驗證")
    ap.add_argument("--rom", default=A.DEFAULT_ROM)
    args = ap.parse_args()
    rom = A.Rom(args.rom)
    pal, tm, tiles = rom.world_map()
    reads = [("vram", PLANE_B, 2 * PLANE_W * 32), ("vram", 32 * A.MAP_TILE_BASE, 32 * A.MAP_TILES), ("cram", 0, 128),
             ("vram", SPRITES, 8 * 80)]
    results = [replay(args.rom, steps, [{"steps": "w10", "at": at, "read": reads}])[0]
               for steps, at in ((SCENARIO_SELECT + HQ_SELECT, 20), (boot(0), MAIN_WAIT))]
    failed = 0
    for (name, row), res in zip([("HQ selection", A.MAP_ROW), ("main", MAIN_ROW)], results):
        plane, vram, cram, sprites = res["read"]
        ok_tiles = sum(vram[32 * i:32 * i + 32] == tiles[32 * i:32 * i + 32] for i in range(A.MAP_TILES))
        cols = [i for i in range(16) if not (name == "main" and i in FLASHING)]
        ok_pal = sum(int.from_bytes(cram[32 + 2 * i:34 + 2 * i], "big") == pal[i] for i in cols)
        cells = [int.from_bytes(plane[2 * ((row + i // A.MAP_W) * PLANE_W + i % A.MAP_W):][:2], "big")
                 for i in range(A.MAP_W * A.MAP_H)]
        shown = [i for i, e in enumerate(cells) if e & 0x7FF >= A.MAP_TILE_BASE]  # frame tiles are below 0x180
        ok_tm = sum(cells[i] == tm[i] + A.MAP_TILE_BASE for i in shown)
        line = (f"{name}: tiles {ok_tiles}/{A.MAP_TILES}, CRAM line 1 {ok_pal}/{len(cols)}, "
                f"plane B row {row} {ok_tm}/{len(shown)} (of {len(cells)})")
        ok = ok_tiles == A.MAP_TILES and ok_pal == len(cols) and ok_tm == len(shown) and len(shown) > 400
        if name == "HQ selection":
            spr = [sprites[8 * k:8 * k + 8] for k in range(2, 2 + A.CITY_COUNT)]
            ok_spr = sum(int.from_bytes(s[4:6], "big") & 0x7FF == MARKER_TILE
                         and (int.from_bytes(s[6:8], "big") - 128, int.from_bytes(s[0:2], "big") - 128)
                         == (c["x"], c["y"] + 24) for s, c in zip(spr, rom.cities()))
            line += f", city markers {ok_spr}/{A.CITY_COUNT}"
            ok &= ok_spr == A.CITY_COUNT
        failed += not ok
        print(line + ("" if ok else "  NG"))
    print("ALL OK" if not failed else f"{failed} screen(s) differ")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
