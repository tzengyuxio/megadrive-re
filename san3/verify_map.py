#!/usr/bin/env python3
"""Check rom.py's strategic map against the game's 情報 → 密偵 screen (the whole map on plane B).

Scenario 1 is played as 劉備 up to the command menu, then 情報 → 密偵. From the VRAM / CRAM / screenshot:
1. tiles: VRAM tiles 0x400-0x6A0 = the 0x2A1 tiles at MAP_TILES;
2. palette: CRAM line 1 = MAP_PALETTE;
3. name table: plane B (VRAM 0xE000, rows 64-91, columns 1-30) = MAP, except the province cells, where the game
   puts marker tile 0x3BC + province id — so each marker also checks Rom.map_cells;
4. screenshot: every map pixel (province cells left out) that isn't covered by plane A or a sprite, against
   Rom.map_rgb.

Usage: .venv/bin/python san3/verify_map.py [--rom ROM] [--keep DIR]
"""
import argparse
import os
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from drive import schedule
from mame import run

TO_MAP = ("w1500 a:20 w200 start:30 w300 w20 w300 w20 w300 start:5 w300 c:10 w300 c:10 w300 up:6 w30 c:10 w300"
          " right:6 w30 right:6 w30 c:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w600 w600 w600"
          " c:10 w200 b:10 w120 down:6 w30 down:6 w30 down:6 w30 c:10 w120 c:10 w200")
PLANE = 0xE000   # planes A and B share the 32 x 128 table; B is scrolled down 64 rows (VSRAM 0x200)
B_ROW, B_COL = 64, 1
MARKER = 0x3BC
SAT = 0xDC00


def capture(rom_path: str, prefix: str) -> None:
    events, end = schedule(TO_MAP.split())
    rows = ",".join(f'{{{f},"{k}","{v}"}}' for f, k, v in events)
    lua = f"""
local ev={{{rows}}}
on_frame(function(f)
  for _,e in ipairs(ev) do if e[1]==f then press(e[3], e[2]=="press") end end
  if f=={end} then shot("{prefix}.png"); dump("{prefix}"); quit() end
end)
"""
    run(rom_path, lua)


def sprite_cover(vram: bytes) -> set[tuple[int, int]]:
    """Screen pixels inside any sprite of the sprite table (linked list from entry 0)."""
    out, i = set(), 0
    for _ in range(80):
        e = vram[SAT + 8 * i:SAT + 8 * i + 8]
        y, size, link, x = R.be16(e, 0) - 128, e[2], e[3] & 0x7F, R.be16(e, 6) - 128
        w, h = ((size >> 2 & 3) + 1) * 8, ((size & 3) + 1) * 8
        out |= {(x + dx, y + dy) for dx in range(w) for dy in range(h)}
        if not link:
            break
        i = link
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="大地圖：密偵畫面的 VRAM／CRAM／截圖對 rom.py 比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--keep", help="把模擬器輸出留在這個資料夾")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    with tempfile.TemporaryDirectory() as tmp:
        folder = args.keep or tmp
        os.makedirs(folder, exist_ok=True)
        prefix = os.path.join(folder, "map")
        capture(args.rom, prefix)
        with open(prefix + ".vram", "rb") as fh:
            vram = fh.read()
        with open(prefix + ".cram", "rb") as fh:
            cram = fh.read()
        im = Image.open(prefix + ".png").convert("RGB")

    n_tiles = R.MAP_TILE_COUNT * 32
    tiles_ok = vram[32 * R.MAP_TILE_BASE:32 * R.MAP_TILE_BASE + n_tiles] == rom.data[R.MAP_TILES:R.MAP_TILES + n_tiles]
    pal_ok = cram[32:64] == rom.data[R.MAP_PALETTE:R.MAP_PALETTE + 32]
    print(f"tiles 0x{R.MAP_TILE_COUNT:X} 張：{'OK' if tiles_ok else 'NG'}；調色盤（CRAM 第 1 列）：{'OK' if pal_ok else 'NG'}")

    words = rom.map_words()
    cells = rom.map_cells()
    province_at = {c: k + 1 for k, c in enumerate(cells) if c}
    plain = same = markers = 0
    other = []
    for y in range(R.MAP_H):
        for x in range(R.MAP_W):
            got = R.be16(vram, PLANE + 2 * (32 * (B_ROW + y) + B_COL + x))
            if words[y][x] == R.MAP_PROVINCE_TILE:
                if (x, y) in province_at and got == MARKER + province_at[(x, y)]:
                    markers += 1
                else:
                    other.append(((x, y), f"0x{got:X}"))
            else:
                plain += 1
                same += got == words[y][x]
    print(f"name table：一般格 {same}/{plain} 相同；州格 {markers}/{len(province_at)} 是該州的標記 tile"
          f"（0x{MARKER:X} + 州 id）；其他州格 {other}")

    rgb = rom.map_rgb()
    w = R.MAP_W * 8
    covered = sprite_cover(vram)
    px = im.load()
    n = ok = 0
    for y in range(R.MAP_H * 8):
        for x in range(w):
            sx, sy = (B_COL * 8 + x), y
            if words[y // 8][x // 8] == R.MAP_PROVINCE_TILE or (sx, sy) in covered:
                continue
            if R.be16(vram, PLANE + 2 * (32 * (sy // 8) + sx // 8)) & 0x7FF:  # plane A drawn there
                continue
            n += 1
            ok += px[sx, sy] == rgb[y * w + x]
    print(f"截圖：可見的地圖 pixel {ok}/{n} 相同")
    good = tiles_ok and pal_ok and same == plain and markers == len(province_at) and ok == n
    print("OK" if good else "MISMATCH")
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
