#!/usr/bin/env python3
"""Check the kanji font decode (rom.glyph_offset / Rom.glyph) against what the game draws, in MAME.

The ruler pick of scenario 1 (session.MAP) lists the first 6 rulers (persons 0-5) with 2-kanji names drawn as
16x16 glyphs into VRAM tiles 0x140- (8 tiles per name: TL TR BL BR of each kanji, colour 15 on 0). From a
savestate just before that screen, the 6 names in the ROM name table are replaced by 2 codes each and the
screen is drawn; every code of the name table (387) and every code used by the game's names is shown once.
Each drawn glyph must equal Rom.glyph bit for bit (set bits colour 15, others 0). About 30 seconds.

Usage: .venv/bin/python san2/verify_text.py [--rom ROM]
"""
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import DEFAULT_ROM, NAME_SIZE, NAME_TABLE, Rom, decode_tile
from session import MAP

NAME_TILES, SLOTS = 0x140, 6
PRE, STEPS = MAP.rsplit(" c:10 w200", 1)[0], "c:10 w200"


def drawn(vram: bytes, slot: int, k: int) -> list[list[int]]:
    """16x16 colour numbers of kanji k of list slot `slot`."""
    base = NAME_TILES + 8 * slot + 4 * k
    tiles = [decode_tile(vram[32 * (base + t):32 * (base + t) + 32]) for t in range(4)]
    return [[tiles[y // 8 * 2 + x // 8][y % 8 * 8 + x % 8] for x in range(16)] for y in range(16)]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證字型解碼（遊戲畫面上的人名字形）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    codes = sorted({c for p in rom.persons() for c in p["kanji_codes"]})
    pairs = [codes[i:i + 2] + codes[:2 - len(codes[i:i + 2])] for i in range(0, len(codes), 2)]
    runs = [pairs[i:i + SLOTS] for i in range(0, len(pairs), SLOTS)]

    def patch(group: list[list[int]]) -> dict:
        rom_patch = [(NAME_TABLE + NAME_SIZE * s, bytes([b for c in pair for b in (c >> 8, c & 255)] + [0]))
                     for s, pair in enumerate(group)]
        return {"rom": rom_patch, "steps": STEPS, "at": 200, "read": [("vram", 0, 0x10000)]}

    parts = [runs[k::4] for k in range(4)]
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(lambda p: replay(args.rom, PRE, [patch(g) for g in p]), parts))
    bad, shown = [], 0
    for part, res in zip(parts, results):
        for group, r in zip(part, res):
            for s, pair in enumerate(group):
                for k, c in enumerate(pair):
                    want = [[15 if b else 0 for b in row] for row in rom.glyph(c)]
                    shown += 1
                    if drawn(r["read"][0], s, k) != want:
                        bad.append(f"{c:04X}")
    print(f"[font] {shown - len(bad)}/{shown} drawn glyphs equal the ROM font ({len(codes)} codes)"
          + (f" NG {sorted(set(bad))[:10]}" if bad else ""))
    print("ALL OK" if not bad else f"{len(bad)} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
