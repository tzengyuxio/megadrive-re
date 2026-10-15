#!/usr/bin/env python3
"""Check the text decode (rom.Rom.codes, rom.Rom.glyph: the font address of every glyph code) against the game
(MAME, about 1.5 minutes).

On the daimyo selection map of scenario 1, C on 尾張 opens "織田信長でよろしいですね". The game draws the name
glyph by glyph into VRAM tiles 0x200, 0x204, ... (4 tiles each: TL TR BL BR, 1bpp font expanded to 4bpp).
Nobunaga's family and given name (general 119 in RAM: $FF27C2 + 40 * 119 + 4 / + 11, 7 bytes each) are
patched with three glyph codes each per run, so that all 868 codes 0x8141-0x84A4 are drawn once; codes with low
byte 00 (0x8200 / 0x8300 / 0x8400) are written as their escapes 0x85F0 / 0x85F1 / 0x85F2. The ink mask of
each drawn tile must equal the glyph rom.Rom.glyph decodes for that code. The unpatched run must draw 織田信長.
(Which character each glyph is, data/charset.txt, was matched by eye: see export.py's font.png.)

Usage: .venv/bin/python bushou/verify_text.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import (
    DEFAULT_ROM,
    GENERAL_SIZE,
    GENERAL_START,
    GLYPH_COUNT,
    RAM_BASE,
    TEXT_BASE,
    ZERO_ESCAPE,
    Rom,
    decode_tile,
)

BOOT = ("w3500 start:10 w300 start:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w300 "
        "up:6 w60 c:10 w300")  # title -> scenario 1, 入門, 初級, 1 player -> daimyo selection map
NOBUNAGA = 119
NAME_RAM = 0xFF0000 + RAM_BASE + GENERAL_START + GENERAL_SIZE * NOBUNAGA + 4
TEXT_TILE = 0x200


def encode(code: int) -> bytes:
    if code & 0xFF == 0:
        code = ZERO_ESCAPE + (code >> 8) - 0x82
    return code.to_bytes(2, "big")


def drawn_masks(vram: bytes, n: int) -> list[list[list[int]]]:
    """Ink masks (16 x 16) of the first n glyphs drawn from TEXT_TILE on."""
    out = []
    for k in range(n):
        m = [[0] * 16 for _ in range(16)]
        for q in range(4):
            px = decode_tile(vram[32 * (4 * k + q):32 * (4 * k + q + 1)])
            for i, v in enumerate(px):
                m[q // 2 * 8 + i // 8][q % 2 * 8 + i % 8] = 1 if v else 0
        out.append(m)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證文字碼與字型位址")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only the first 10 runs and the escapes")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    codes = [TEXT_BASE + g for g in range(GLYPH_COUNT)]
    groups = [codes[k:k + 6] for k in range(0, len(codes), 6)]
    if args.quick:
        groups = groups[:10] + [[0x8200, 0x8300, 0x8400]]
    read = [("vram", TEXT_TILE * 32, 6 * 128)]
    runs = [{"steps": "c:10 w200", "at": 220, "read": read}]
    for grp in groups:
        fam, giv = grp[:3], grp[3:]
        name = (b"".join(map(encode, fam)) + b"\0").ljust(7, b"\0") + (b"".join(map(encode, giv)) + b"\0").ljust(7, b"\0")
        runs.append({"ram": [(NAME_RAM, name)], "steps": "c:10 w200", "at": 220, "read": read})
    res = replay(args.rom, BOOT, runs)
    errors = 0
    rec = rom.general_record(0, NOBUNAGA)
    natural = rom.codes(rec[4:11]) + rom.codes(rec[11:18])
    want = [rom.glyph(c - TEXT_BASE) for c in natural]
    ok = drawn_masks(res[0]["read"][0], len(natural)) == want
    print(f"[natural] {rom.text(rec[4:11])}{rom.text(rec[11:18])} ({' '.join(f'{c:04X}' for c in natural)}) drawn: "
          + ("OK" if ok else "NG"))
    errors += not ok
    bad = []
    for grp, r in zip(groups, res[1:]):
        got = drawn_masks(r["read"][0], len(grp))
        bad += [c for c, m in zip(grp, got) if m != rom.glyph(c - TEXT_BASE)]
    n = sum(len(g) for g in groups)
    print(f"[glyphs] {n - len(bad)}/{n} codes drawn as rom.Rom.glyph(code - 0x8141)"
          + (f" (NG {[hex(c) for c in bad[:20]]})" if bad else ""))
    esc_ok = not any(c & 0xFF == 0 for c in bad)
    print(f"[escape] 85F0/85F1/85F2 -> 8200/8300/8400: {'OK' if esc_ok else 'NG'}")
    errors += len(bad)
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
