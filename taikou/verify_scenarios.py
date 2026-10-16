#!/usr/bin/env python3
"""Check the start-of-game data (rom.INIT_SEGMENTS and the tables in it) against the game.

A new game is started in MAME up to the type selection screen. By then the game has cleared RAM and copied the six
ROM segments of INIT_SEGMENTS (unsolved header tables, factions, persons, castle states); RAM $FF0040-$FF4611 is
read back and compared byte by byte with rom.Rom.init_image. Then the faction (20 x 34 at $FF0248), person
(241 x 60 at $FF04F0) and castle state (123 x 18 at $FF3D6C) tables are compared record by record. Known
difference: the game has already set bit 4 of castle state +15 (the castle icon bits) of castles 68 and 72; it is
reported and not counted.

Usage: .venv/bin/python taikou/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from replay import replay

TO_TYPES = "w1500 start:10 w200 start:10 w200 c:10 w300"   # title → 新たな物語を始める → type selection
LO, HI = 0xFF0040, R.CASTLE_STATE_RAM + R.CASTLE_STATE_SIZE * R.CASTLE_STATE_COUNT
KNOWN = {R.CASTLE_STATE_RAM + R.CASTLE_STATE_SIZE * c + 15: 0x10 for c in (68, 72)}   # address: bits set


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證開局初始資料")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    (res,) = replay(args.rom, TO_TYPES, [{"at": 60, "read": [("ram", LO, HI - LO)]}])
    ram = res["read"][0]
    want = rom.init_image(LO, HI - LO)
    copied = [i for i in range(HI - LO) if want[i] is not None]
    known = [i for i in copied if LO + i in KNOWN and ram[i] == want[i] | KNOWN[LO + i]]
    diff = [i for i in copied if ram[i] != want[i] and i not in known]
    print(f"[segments] {len(copied) - len(diff) - len(known)}/{len(copied)} copied bytes of ${LO:06X}-${HI - 1:06X} "
          f"equal the ROM" + (f" (differences at {[hex(LO + i) for i in diff[:10]]})" if diff else ""))
    print(f"  known: {len(known)} castle state bytes with bit 4 already set "
          f"({', '.join(f'castle {(LO + i - R.CASTLE_STATE_RAM) // R.CASTLE_STATE_SIZE}' for i in known)})")
    errors = len(diff)
    for label, ram_addr, rom_addr, count, size in (
            ("factions", R.FACTION_RAM, R.FACTIONS, R.FACTION_COUNT, R.FACTION_SIZE),
            ("persons", R.PERSON_RAM, R.PERSONS, R.PERSON_COUNT, R.PERSON_SIZE),
            ("castle states", R.CASTLE_STATE_RAM, R.CASTLE_STATES, R.CASTLE_STATE_COUNT, R.CASTLE_STATE_SIZE)):
        o = ram_addr - LO
        ok = sum(all(ram[o + size * k + j] == rom.data[rom_addr + size * k + j] or o + size * k + j in known
                     for j in range(size)) for k in range(count))
        print(f"[{label}] {ok}/{count} records of {size} bytes at ${ram_addr:06X} equal ROM 0x{rom_addr:X}")
        errors += count - ok
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
