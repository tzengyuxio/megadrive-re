#!/usr/bin/env python3
"""Verify the main screen / strategy map decoding against the game: scenario 1, 1 player, house selection screen.
Compares
- VRAM tiles MAP_TILE_BASE.. (0x1A1 tiles) with MAP_TILES_ROM and CRAM line 2 with MAP_PALETTE;
- the window plane ($F000, 32 cells wide) at screen cell (1, 0) with SCREEN_LAYOUTS[0], cell by cell (text, the
  face and the house list are drawn over parts of it, so only the map cells must all match);
- the screenshot at (128, 24) with rom.map_rgb, pixel by pixel, outside the 30 province mark cells (house marks and
  numbers are drawn there).

Usage: .venv/bin/python royal/verify_map.py [--rom ROM]
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
from verify_faces import PLAYERS_MENU

WINDOW, WINDOW_W = 0xF000, 32


def main() -> None:
    ap = argparse.ArgumentParser(description="主畫面與戰略地圖的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    tiles = R.MAP_TILE_COUNT * 32
    res = replay(args.rom, PLAYERS_MENU, [{"steps": "c:4 w220", "at": 240, "shot": True,
                                          "read": [("vram", R.MAP_TILE_BASE * 32, tiles), ("cram", 64, 32),
                                                   ("vram", WINDOW, WINDOW_W * 2 * R.SCREEN_H)]}])[0]
    vram, cram, window = res["read"]
    tiles_ok = vram == rom.data[R.MAP_TILES_ROM:R.MAP_TILES_ROM + tiles]
    cram_ok = cram == rom.data[R.MAP_PALETTE:R.MAP_PALETTE + 32]
    lay = rom.screen_layout(0)
    sx, sy = R.SCREEN_AT
    mx, my, mw, mh = R.MAP_CELLS
    same = {(x, y) for y in range(R.SCREEN_H) for x in range(R.SCREEN_W)
            if int.from_bytes(window[2 * ((sy + y) * WINDOW_W + sx + x):][:2], "big") == lay[y * R.SCREEN_W + x]}
    map_cells = {(mx + x, my + y) for y in range(mh) for x in range(mw)}
    im = Image.open(res["shot"]).convert("RGB")
    w, h, px = rom.map_rgb()
    marks = {rom.province_mark(k) for k in range(R.PROVINCE_COUNT)}
    ox, oy = 8 * (sx + mx), 8 * (sy + my)
    checked = [(x, y) for y in range(h) for x in range(w) if (x // 8, y // 8) not in marks]
    diff = [(x, y) for x, y in checked if im.getpixel((ox + x, oy + y)) != px[y * w + x]]
    print(f"VRAM tiles {R.MAP_TILE_BASE:#x}+{R.MAP_TILE_COUNT:#x}: {'OK' if tiles_ok else 'NG'}; "
          f"CRAM line 2: {'OK' if cram_ok else 'NG'}")
    print(f"window plane: {len(same)}/{R.SCREEN_W * R.SCREEN_H} cells equal SCREEN_LAYOUTS[0], "
          f"map cells {len(map_cells & same)}/{len(map_cells)}")
    print(f"map screen ({ox}, {oy}) {w}x{h}: {len(checked) - len(diff)}/{len(checked)} pixels equal "
          f"(outside the {len(marks)} mark cells)")
    ok = tiles_ok and cram_ok and map_cells <= same and not diff
    print("ALL OK" if ok else "NG")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
