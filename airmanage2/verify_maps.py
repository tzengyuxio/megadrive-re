#!/usr/bin/env python3
"""Verify the world and area maps against the game.

From a savestate at the head-office area menu (verify_scenarios.SCENARIO_MENU + scenario / YES / level / players),
which shows the world map, and then for each of the 7 areas (picked with the d-pad, C) on the head-office city
screen, which shows the area map: VRAM tiles 1-704 must be the decompressed tiles, CRAM line 1 the palette,
plane B ($E000) the tilemap (except the bottom cells the screen's panels overwrite), and the screenshot
Rom.world_map / Rom.area_map pixel for pixel in those map cells wherever neither plane A nor a sprite draws
over plane B; on the area screens the city marker sprites must sit at CITY_AREA_XY of the area's cities
(tile 0x763 for home cities, 0x765 for the others).

Usage: .venv/bin/python airmanage2/verify_maps.py [--rom ROM]
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
from verify_scenarios import SCENARIO_MENU

PLANE_A, PLANE_B, SPRITES = 0xC000, 0xE000, 0xF000   # VDP registers 2, 4, 5 on these screens (32 x 32 planes)
AREA_KEYS = ["", "down", "right", "right right", "right right down", "left", "left down"]   # from ヨーロッパ


def covered(vram: bytes) -> set[tuple[int, int]]:
    """Screen pixels where plane A or a sprite is opaque."""
    def px(t: int, x: int, y: int) -> int:
        b = vram[32 * t + 4 * y + x // 2]
        return b >> 4 if x % 2 == 0 else b & 15

    out = set()
    for c in range(32 * 28):
        e = int.from_bytes(vram[PLANE_A + 2 * c:PLANE_A + 2 * c + 2], "big")
        for y in range(8):
            for x in range(8):
                if px(e & 0x7FF, 7 - x if e & 0x800 else x, 7 - y if e & 0x1000 else y):
                    out.add((c % 32 * 8 + x, c // 32 * 8 + y))
    s = 0
    for _ in range(80):
        o = SPRITES + 8 * s
        y, size, attr, x = (int.from_bytes(vram[o + k:o + k + 2], "big") for k in (0, 2, 4, 6))
        w, h = (size >> 10 & 3) + 1, (size >> 8 & 3) + 1
        for cx in range(w):
            for cy in range(h):
                tx, ty = (w - 1 - cx if attr & 0x800 else cx), (h - 1 - cy if attr & 0x1000 else cy)
                t = (attr & 0x7FF) + tx * h + ty
                for yy in range(8):
                    for xx in range(8):
                        if px(t, 7 - xx if attr & 0x800 else xx, 7 - yy if attr & 0x1000 else yy):
                            out.add(((x & 0x1FF) - 128 + 8 * cx + xx, (y & 0x3FF) - 128 + 8 * cy + yy))
        s = size & 0x7F
        if s == 0:
            break
    return out


def markers(vram: bytes) -> list[tuple[int, int, int]]:
    """(x, y, tile) of the city marker sprites (tile 0x763 home city, 0x765 other city)."""
    out, s = [], 0
    for _ in range(80):
        o = SPRITES + 8 * s
        y, size, attr, x = (int.from_bytes(vram[o + k:o + k + 2], "big") for k in (0, 2, 4, 6))
        if attr & 0x7FF in (0x763, 0x765):
            out.append(((x & 0x1FF) - 128, (y & 0x3FF) - 128, attr & 0x7FF))
        s = size & 0x7F
        if s == 0:
            break
    return sorted(out)


def check(rom: A.Rom, name: str, res: dict, tiles: bytes, tilemap: int, palette: int, img: list,
          area: int | None = None) -> bool:
    vram, cram = res["read"]
    im = Image.open(res["shot"]).convert("RGB")
    os.remove(res["shot"])
    ok_tiles = vram[32:32 + 704 * 32] == tiles[:704 * 32]
    pal = cram[32:64] == rom.data[palette:palette + 32]
    same = [vram[PLANE_B + 2 * i:PLANE_B + 2 * i + 2] == rom.data[tilemap + 2 * i:tilemap + 2 * i + 2]
            for i in range(A.MAP_W * A.MAP_H)]
    cells = sum(same)
    cov = covered(vram)
    seen = [(x, y) for y in range(8 * A.MAP_H) for x in range(256)
            if (x, y) not in cov and same[y // 8 * A.MAP_W + x // 8]]
    bad = sum(im.getpixel(p) != img[p[1]][p[0]] for p in seen)
    ok = ok_tiles and pal and not bad and cells > 0
    text = ""
    if area is not None:
        want = sorted((c["area_x"], c["area_y"], 0x763 if c["home"] else 0x765) for c in rom.cities()
                      if c["area"] == area)
        ok &= markers(vram) == want
        text = f", city markers {'OK' if markers(vram) == want else 'NG'} ({len(want)})"
    print(f"{name}: tiles {'OK' if ok_tiles else 'NG'}, CRAM line 1 {'OK' if pal else 'NG'}, "
          f"plane B {cells}/{A.MAP_W * A.MAP_H} cells, screen {len(seen) - bad}/{len(seen)} visible pixels{text}"
          + ("" if ok else "  NG"))
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description="大地圖與地區地圖的模擬器驗證")
    ap.add_argument("--rom", default=A.DEFAULT_ROM)
    args = ap.parse_args()
    rom = A.Rom(args.rom)
    reads = [("vram", 0, 0x10000), ("cram", 0, 128)]
    runs = [{"steps": "w10", "at": 10, "shot": True, "read": reads}]
    runs += [{"steps": " ".join(f"{k}:5 w200" for k in keys.split()) + " c:10 w300",
              "at": 205 * len(keys.split()) + 300, "shot": True, "read": reads} for keys in AREA_KEYS]
    res = replay(rom.path, SCENARIO_MENU + "c:10 w300 " * 4, runs)
    ok = check(rom, "world map (area menu)", res[0], rom.world_tiles(), A.WORLD_TILEMAP, A.WORLD_PALETTE,
               rom.world_map())
    names = [a["name"] for a in rom.areas()]
    for a, r in enumerate(res[1:]):
        ok &= check(rom, f"area {a} {names[a]} (head office screen)", r, rom.area_tiles(a), A.AREA_TILEMAP,
                    A.AREA_PALETTE, rom.area_map(a), a)
    print("ALL OK" if ok else "differences found")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
