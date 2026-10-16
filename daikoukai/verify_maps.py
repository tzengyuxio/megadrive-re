#!/usr/bin/env python3
"""Verify the world map decoding against the game: leave Lisboa, and on the "リスボンのみなとをでます" message move
fleet 0 ($FF1778: chunk x, chunk y, metatile x, metatile y) to a test chunk. After the next C the game loads the
area ($858A) and draws the ship's chunk ($86E8) into plane A rows 33-60, columns 2-29. Compared, at the chunk the
fleet is in when read (the fleet keeps sailing): the 28 x 28 name table words (= rom.chunk_words), CRAM line 3
(= one of the set's MAP_PALETTES) and the 224-pixel-wide screen area at x = 16 (= rom.chunk_pixels in that
palette). Plane A is scrolled vertically, so the chunk's rows are matched at the best of the offsets -32..32 around
y = 8 (rows off screen are skipped); the ship sprite is allowed to differ.

Test chunks: the start chunk (fleet not moved) and, per metatile set, the chunk with the most distinct name table words.

Usage: .venv/bin/python daikoukai/verify_maps.py [--rom ROM]
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
from verify_faces import NEW_GAME

# new game → Lisboa → walk to the harbour → しゅっこう → confirm; the "でます" message is next
LEAVE = NEW_GAME + " c:10 w300 " + "c:10 w200 " * 6 + "c:10 w200 down:40 w60 down:40 w100 c:10 w200 c:10 w300 w300"
PLANE_A, PLANE_W, ROW0, COL0 = 0xE000, 32, 33, 2
SCREEN_X, SCREEN_Y = 16, 8
SPRITE_PIXELS = 24 * 24                 # the ship


def screen_match(im: Image.Image, px: bytes, rgb: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    """(matching pixels, compared pixels, y offset) at the best vertical offset."""
    shot = list(zip(*[iter(im.tobytes())] * 3))

    def count(dy: int, step: int) -> tuple[int, int]:
        rows = [y for y in range(0, 224, step) if 0 <= SCREEN_Y + dy + y < im.height]
        n = sum(shot[(SCREEN_Y + dy + y) * im.width + SCREEN_X + x] == rgb[px[y * 224 + x]]
                for y in rows for x in range(224))
        return n, 224 * len(rows)

    dy = max(range(-32, 33), key=lambda d: count(d, 7)[0] / count(d, 7)[1])
    return *count(dy, 1), dy


def test_chunks(rom: R.Rom) -> list[tuple[int, int]]:
    best = {}
    for cy in range(R.MAP_H):
        for cx in range(R.MAP_W):
            n, s = len(set(rom.chunk_words(cx, cy))), rom.map_set(cy)
            if n > best.get(s, (0,))[0]:
                best[s] = (n, cx, cy)
    return [None] + [(cx, cy) for _, cx, cy in best.values()]


def main() -> None:
    ap = argparse.ArgumentParser(description="世界地圖解碼的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    chunks = test_chunks(rom)
    runs = [{"ram": [(0xFF1778, bytes([*c, 7, 7]))] if c else [], "steps": "c:10 w600", "at": 620, "shot": True,
             "read": [("vram", PLANE_A, PLANE_W * 128 * 2), ("ram", 0xFF1778, 4), ("cram", 0x60, 32),
                      ("ram", 0xFF3A8A, 2)]} for c in chunks]
    bad = 0
    for res in replay(args.rom, LEAVE, runs):
        vram, loc, cram, game_set = res["read"]
        nt = [R.be16(vram, 2 * i) for i in range(PLANE_W * 128)]
        words = rom.chunk_words(loc[0], loc[1])
        n_nt = sum(nt[(ROW0 + y) * PLANE_W + COL0 + x] == words[y * R.CHUNK_TILES + x]
                   for y in range(R.CHUNK_TILES) for x in range(R.CHUNK_TILES))
        s = rom.map_set(loc[1])
        pal = [R.be16(cram, 2 * i) for i in range(16)]
        phases = [ph for ph in range(R.MAP_PHASES) if rom.map_palette(s, ph) == pal]
        rgb = [R.md_rgb(w) for w in pal]
        px = rom.chunk_pixels(loc[0], loc[1])
        im = Image.open(res["shot"]).convert("RGB")
        n_px, n_all, dy = screen_match(im, px, rgb)
        os.remove(res["shot"])
        ok = n_nt == R.CHUNK_TILES ** 2 and R.be16(game_set, 0) == s and phases and n_px >= n_all - SPRITE_PIXELS
        bad += not ok
        print(f"chunk ({loc[0]},{loc[1]}) set {s} ($FF3A8A {R.be16(game_set, 0)}) [{len(set(words))} words]: name table {n_nt}/784, "
              f"CRAM line 3 = palette phase {phases}, screen {n_px}/{n_all} (y {SCREEN_Y + dy})" + ("" if ok else "  NG"))
    print(f"maps {len(chunks) - bad}/{len(chunks)} chunks match")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
