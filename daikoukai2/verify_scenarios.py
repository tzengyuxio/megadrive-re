#!/usr/bin/env python3
"""Verify the initial game state against the game: at the hero select the RAM block $FF0000-$FF6E4B must equal the
ROM block INIT (0xD2516, copied by $136FC) byte for byte. It holds the persons, VIPs, women, fleets, ship types,
ports, port state and items that rom.Rom decodes.

Usage: .venv/bin/python daikoukai2/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from replay import replay
from verify_faces import TO_HEROES

TABLES = [("persons", R.PERSONS), ("vips", R.VIPS), ("women", R.WOMEN), ("ship_types", R.SHIP_TYPES),
          ("ports", R.PORTS), ("port_state", R.PORT_STATE),
          ("items", R.ITEMS)]


def main() -> None:
    ap = argparse.ArgumentParser(description="初始資料區塊（人物、港口、船種、道具等）的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    ram = replay(args.rom, TO_HEROES, [{"steps": "", "at": 1, "read": [("ram", R.INIT_RAM, R.INIT_SIZE)]}])[0]["read"][0]
    init = rom.data[R.INIT:R.INIT + R.INIT_SIZE]
    diff = [i for i in range(R.INIT_SIZE) if ram[i] != init[i]]
    print(f"[block] $FF0000 +{R.INIT_SIZE:#x}: {R.INIT_SIZE - len(diff)}/{R.INIT_SIZE} bytes equal ROM 0x{R.INIT:X}"
          + (f" (differ: {', '.join(f'+{i:#x}' for i in diff[:10])})" if diff else ""))

    for name, at in TABLES:
        print(f"  {name}: RAM ${R.ram(at):06X} (ROM 0x{at:X}) inside the block")
    ok = not diff
    print("ALL OK" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
