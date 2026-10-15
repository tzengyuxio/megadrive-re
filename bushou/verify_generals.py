#!/usr/bin/env python3
"""Check the general fields against the game screen (MAME, about 15 seconds).

Scenario 1 as 織田信長: on the province screen of 尾張, 開発 -> C opens the general list (name, 政治 戦闘 教養
魅力, one general per two tile rows from row 4, sorted by 政治 descending). The screen is read back from plane A (nametable 0xE000): the
name glyphs are 4 tiles each (TL TR / BL BR) whose ink masks are looked up in the font (rom.Rom.glyph), the
numbers are digit tiles 0xD0 + 2 d (top half; 0xB0 = blank).
  natural run: the list must show 尾張's generals (rom.Rom.provinces members) with names and the four values of
               rom.Rom.generals;
  patched runs: the seven records in RAM ($FF27C2 + 40 i) get random names (+4 / +11) and random values
               (+19 .. +22) before the screen opens; the list must show exactly those.
Rows are compared as a set (ties in 政治 have no defined order) and must be in 政治 descending order.

Usage: .venv/bin/python bushou/verify_generals.py [--rom ROM] [--runs N]
"""
import argparse
import os
import random
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
    be16,
    decode_tile,
)

BOOT = ("w3500 start:10 w300 start:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w300 up:6 w60 c:10 w300 "
        "c:10 w300 left:10 w200 c:10 w200 left:10 w400")  # -> province screen of 尾張 (scenario 1, 織田信長)
STEPS, AT = "c:10 w200 c:10 w200", 440                       # 開発 -> general list
OWARI = 23
PLANE, PLANE_W, FIRST_ROW = 0xE000, 32, 4
NAME_COLS = range(3, 13, 2)
VALUE_COLS = [15, 19, 23, 27]                                  # 3 digit cells each: 政治 戦闘 教養 魅力
DIGIT0, BLANK = 0xD0, 0xB0


def encode(g: int) -> bytes:
    code = TEXT_BASE + g
    if code & 0xFF == 0:
        code = ZERO_ESCAPE + (code >> 8) - 0x82
    return code.to_bytes(2, "big")


def gen_ram(i: int) -> int:
    return 0xFF0000 + RAM_BASE + GENERAL_START + GENERAL_SIZE * i


def read_list(rom: Rom, vram: bytes, rows: int, masks: dict) -> list[tuple[str, list[int]]]:
    def cell(c: int, r: int) -> int:
        return be16(vram, PLANE + 2 * (r * PLANE_W + c)) & 0x7FF

    out = []
    for k in range(rows):
        r = FIRST_ROW + 2 * k
        name = ""
        for c in NAME_COLS:
            tiles = [cell(c, r), cell(c + 1, r), cell(c, r + 1), cell(c + 1, r + 1)]
            if tiles[0] in (0, BLANK):
                break
            m = tuple(tuple(1 if v else 0 for v in decode_tile(vram[32 * t:32 * t + 32])) for t in tiles)
            name += masks.get(m, "？")
        values = []
        for c in VALUE_COLS:
            ds = [cell(c + j, r) for j in range(3)]
            values.append(int("".join(str((t - DIGIT0) // 2) for t in ds if t != BLANK) or "-1"))
        out.append((name, tuple(values)))
    return out


def glyph_masks(rom: Rom) -> dict:
    out = {}
    for g in range(GLYPH_COUNT):
        gl = rom.glyph(g)
        key = tuple(tuple(gl[q // 2 * 8 + i // 8][q % 2 * 8 + i % 8] for i in range(64)) for q in range(4))
        out.setdefault(key, rom.charset[g])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證武將欄位與遊戲畫面一致")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--runs", type=int, default=4, help="patched runs")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    gens = rom.generals(0)
    members = rom.provinces(0)[OWARI]["generals"]
    masks = glyph_masks(rom)
    # glyphs with a unique mask whose character is known, for random names
    usable = [g for g in range(GLYPH_COUNT) if rom.charset[g] != "〓" and masks.get(
        tuple(tuple(rom.glyph(g)[q // 2 * 8 + i // 8][q % 2 * 8 + i % 8] for i in range(64)) for q in range(4)))
        == rom.charset[g]]
    rng = random.Random(1991)
    read = [("vram", 0, 0x10000)]
    runs, expect = [{"steps": STEPS, "at": AT, "read": read}], []
    expect.append([(gens[i]["name"], tuple(gens[i][k] for k in ("politics", "war", "culture", "charm"))) for i in members])
    for _ in range(args.runs):
        ram, want = [], []
        for i in members:
            fam, giv = rng.sample(usable, 2), rng.sample(usable, 2)
            vals = [rng.randrange(1, 101) for _ in range(4)]
            enc = b"".join(map(encode, fam)) + b"\0\0\0"
            enc += b"".join(map(encode, giv)) + b"\0\0\0"
            ram += [(gen_ram(i) + 4, enc), (gen_ram(i) + 19, bytes(vals))]
            want.append(("".join(rom.charset[g] for g in fam + giv), tuple(vals)))
        runs.append({"ram": ram, "steps": STEPS, "at": AT, "read": read})
        expect.append(want)
    res = replay(args.rom, BOOT, runs)
    errors = 0
    for n, (r, want) in enumerate(zip(res, expect)):
        got = read_list(rom, r["read"][0], len(members), masks)
        ok = sorted(got) == sorted(want) and [g[1][0] for g in got] == sorted((w[1][0] for w in want), reverse=True)
        errors += not ok
        label = "natural" if n == 0 else f"patched {n}"
        print(f"[{label}] {len(set(got) & set(want))}/{len(want)} rows equal: "
              + " ".join(f"{g[0]}{g[1]}" for g in got[:3]) + " …" + ("" if ok else f" NG want {want}"))
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
