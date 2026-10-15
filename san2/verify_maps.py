#!/usr/bin/env python3
"""Check the big map and the 41 battle fields against the game in MAME (about 1 minute).

1. Big map (session.WAR_MAP, 袁術 picking where to attack): plane A must show tiles 0x1D0- of MAP_TILEMAP at
   cell (2, 3) except where the game draws province numbers, flags or windows over it; every tile 0x1D0-0x380 in VRAM
   must equal ROM MAP_TILES and CRAM line 0 must equal MAP_PALETTE.
2. Battle fields (session.BATTLE, 袁術 attacking province 20): each field is patched into the ROM in place
   of field 20 (one MAME run per field, in parallel) and the game lays it out; each hex's 4 plane entries
   (hex column c, row r at cell (3 + 2c, 3 + 2r + c % 2)) must equal TERRAIN_CELLS of its terrain. Hexes
   covered by units, the message window, or the attacker's entry marks (tile 0x1F3 in the top-right cell)
   are counted apart. The terrain tiles in VRAM (river: any of its 4 animation frames) and CRAM lines 0-1
   must equal the ROM.

Usage: .venv/bin/python san2/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rom import (
    BATTLE,
    BATTLE_COLS,
    BATTLE_PALETTES,
    BATTLE_ROWS,
    DEFAULT_ROM,
    MAP_FIRST_TILE,
    MAP_H,
    MAP_PALETTE,
    MAP_TILES,
    MAP_W,
    PROVINCE_COUNT,
    Rom,
)
from session import BATTLE as BATTLE_KEYS
from session import WAR_MAP, play

PLANE, MAP_X, MAP_Y = 0xE000, 2, 3
TARGET = 19                        # field 20 is the one the game loads for this battle
ENTRY_MARK = 0x1F3


def entry(vram: bytes, x: int, y: int) -> int:
    a = PLANE + 2 * (32 * y + x)
    return vram[a] << 8 | vram[a + 1]


def check_map(rom: Rom, m: dict[str, bytes]) -> int:
    d, vram, errors = rom.data, m["vram"], 0
    if m["cram"][:32] != d[MAP_PALETTE:MAP_PALETTE + 32]:
        print("  NG palette")
        errors += 1
    last = max(n & 0x7FF for n in rom.map_tilemap())
    bad_tiles = [n for n in range(MAP_FIRST_TILE, last + 1)
                 if vram[32 * n:32 * n + 32] != d[MAP_TILES + 32 * (n - MAP_FIRST_TILE):][:32]]
    same = covered = 0
    for i, n in enumerate(rom.map_tilemap()):
        e = entry(vram, MAP_X + i % MAP_W, MAP_Y + i // MAP_W)
        if e == n:
            same += 1
        elif not MAP_FIRST_TILE <= e & 0x7FF <= last:
            covered += 1          # province numbers, flags, windows drawn over the map
        else:
            print(f"  NG cell {i}: {e:04X} (ROM {n:04X})")
            errors += 1
    errors += len(bad_tiles)
    print(f"[map] tilemap {same}/{MAP_W * MAP_H} cells equal the ROM, {covered} covered by labels/flags/windows;"
          f" tiles {last + 1 - MAP_FIRST_TILE - len(bad_tiles)}/{last + 1 - MAP_FIRST_TILE} equal;"
          f" palette {'OK' if m['cram'][:32] == d[MAP_PALETTE:MAP_PALETTE + 32] else 'NG'}"
          + (f" (NG tiles {[hex(n) for n in bad_tiles[:8]]})" if bad_tiles else ""))
    return errors


def check_battle_gfx(rom: Rom, m: dict[str, bytes]) -> int:
    d, vram = rom.data, m["vram"]
    entries = sorted({e & 0x7FF for cells in rom.terrain_cells() for e in cells})
    bad = [f"{n:03X}" for n in entries
           if all(vram[32 * n:32 * n + 32] != d[rom.battle_tile_offset(n, f):][:32] for f in range(4))]
    want = b"".join(d[o:o + 32] for o in BATTLE_PALETTES)
    pal_ok = m["cram"][:64] == want
    print(f"[battle] {len(entries) - len(bad)}/{len(entries)} terrain tiles match the ROM, CRAM lines 0-1 "
          + ("OK" if pal_ok else "NG") + (f" (NG {' '.join(bad)})" if bad else ""))
    return len(bad) + (not pal_ok)


def check_field(rom: Rom, i: int, vram: bytes) -> tuple[int, int, int, set[int]]:
    """(matching hexes, covered hexes, wrong hexes, entry-marked hexes) of field i laid out by the game."""
    cells, ok, covered, wrong, marks = rom.terrain_cells(), 0, 0, 0, set()
    terrain_tiles = {e & 0x7FF for c in cells for e in c}
    for r, row in enumerate(rom.battle_terrain(i)):
        for c, t in enumerate(row):
            x, y = 3 + 2 * c, 3 + 2 * r + c % 2
            got = [entry(vram, x + k % 2, y + k // 2) for k in range(4)]
            w = cells[t]
            if got == w:
                ok += 1
            elif got == [w[0], got[1], w[2], w[3]] and got[1] & 0x7FF == ENTRY_MARK:
                ok += 1
                marks.add(BATTLE_COLS * r + c)
            elif any(g != v and (g & 0x7FF) in terrain_tiles for g, v in zip(got, w)):
                wrong += 1
            else:
                covered += 1      # unit sprites drawn into the plane, the message window
    return ok, covered, wrong, marks


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖與戰場地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    d = rom.data

    def run_field(i: int) -> dict[str, bytes]:
        field = ",".join(str(b) for b in d[BATTLE + 78 * i:BATTLE + 78 * i + 78])
        lua = f"on_frame(function(f) if f==1 then rom_write({BATTLE + 78 * TARGET}, string.char({field})) end end)\n"
        return play(args.rom, BATTLE_KEYS + " @b", lua)["b"]

    with ThreadPoolExecutor(8) as ex:
        big = ex.submit(lambda: play(args.rom, WAR_MAP + " @m")["m"])
        fields = list(ex.map(run_field, range(PROVINCE_COUNT)))
    errors = check_map(rom, big.result())
    errors += check_battle_gfx(rom, fields[TARGET])
    bad, total_cov, marks = [], 0, set()
    for i, m in enumerate(fields):
        ok, covered, wrong, mk = check_field(rom, i, m["vram"])
        total_cov += covered
        marks |= mk
        if wrong or ok + covered != BATTLE_COLS * BATTLE_ROWS:
            bad.append(f"{i + 1}({wrong})")
    print(f"[battle] {PROVINCE_COUNT - len(bad)}/{PROVINCE_COUNT} fields match the game's plane"
          f" ({total_cov} hexes covered by units/window in all, entry marks at hexes {sorted(marks)})"
          + (f" NG {bad}" if bad else ""))
    errors += len(bad)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
