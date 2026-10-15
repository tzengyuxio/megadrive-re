#!/usr/bin/env python3
"""Check the font (Rom.font_codes / Rom.glyph) against what the game draws for every character code.

Same run as verify_persons.py (all 531 persons in 劉備's 武将一覧, 8 rows per page), but the person names in the
cartridge ROM are first overwritten with the font's codes, 3 per name (2 runs cover all 2150 codes; the last
code 0xFF07 is the table's end mark, and codes with an empty glyph are left out). The three 16x16 cells of each
name (x = 24, 40, 56) are cut from the screenshot and compared pixel for pixel with the glyph rom.py assigns to
the code: the game looks the code up itself ($C4A0 binary search, $C4EE glyph copy).

Usage: .venv/bin/python san3/verify_text.py [--rom ROM] [--keep DIR]
"""
import argparse
import os
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rom as R
from verify_persons import BG, LIU_BEI, ROW_Y, ROWS, capture

NAME_X = 24
PER_NAME = 3


def main() -> None:
    ap = argparse.ArgumentParser(description="字型：每個文字碼換進人名，比對遊戲畫出的字形")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--keep", help="把截圖留在這個資料夾")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    codes = rom.font_codes()
    glyphs = {code: rom.glyph(i) for i, code in enumerate(codes[:-1])}
    todo = [c for c, g in glyphs.items() if any(any(r) for r in g)]
    chain = [LIU_BEI] + [p for p in range(R.SCEN_PERSON_COUNT) if p != LIU_BEI]
    n_pages = -(-len(chain) // ROWS)
    per_run = len(chain) * PER_NAME
    ok, bad = 0, []
    with tempfile.TemporaryDirectory() as tmp:
        for run_no, start in enumerate(range(0, len(todo), per_run)):
            batch = todo[start:start + per_run]
            names = {pid: batch[PER_NAME * i:PER_NAME * (i + 1)] for i, pid in enumerate(chain)}
            patch = {R.PERSONS + R.PERSON_SIZE * pid + 15: b"".join(c.to_bytes(2, "big") for c in cs).ljust(7, b"\0")
                     for pid, cs in names.items()}
            folder = os.path.join(args.keep or tmp, f"run{run_no}")
            os.makedirs(folder, exist_ok=True)
            capture(args.rom, chain, folder, n_pages, n_cols=1, patch=patch)
            for page in range(n_pages):
                px = Image.open(os.path.join(folder, f"c0p{page}.png")).convert("RGB").load()
                for r in range(ROWS):
                    i = page * ROWS + r
                    if i >= len(chain):
                        break
                    for j, code in enumerate(names[chain[i]]):
                        x0, y0 = NAME_X + 16 * j, ROW_Y + 16 * r
                        cell = [[int(px[x0 + x, y0 + y] != BG) for x in range(16)] for y in range(16)]
                        if cell == glyphs[code]:
                            ok += 1
                        else:
                            bad.append(f"{code:04X}")
    print(f"字型：{ok}/{len(todo)} 個文字碼的字形與遊戲畫面相同（另 {len(glyphs) - len(todo)} 個空白字形未比）")
    if bad:
        print("  NG", " ".join(bad[:40]))
    good = ok == len(todo)
    print("OK" if good else "MISMATCH")
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
