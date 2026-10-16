#!/usr/bin/env python3
"""Verify the initial game state against the game: after a new game (default name, bonus points spent) the RAM
block $FF1000-$FF221A must equal the ROM block INIT (0xE3E48, copied by memcpy $0688) byte for byte, except the
player's 5 abilities ($FF1D0F-$FF1D13, rerolled when the bonus points are handed out). The block holds the
persons, fleets, abilities, the player's name and the building flags that rom.Rom decodes.

Usage: .venv/bin/python daikoukai/verify_persons.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from replay import replay
from verify_faces import NEW_GAME

REROLLED = range(R.STAT_START + 1, R.STAT_START + 1 + len(R.STATS) - 1)   # player: leadership .. strength


def main() -> None:
    ap = argparse.ArgumentParser(description="初始資料區塊（人物、艦隊、能力、建物旗標）的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    ram = replay(args.rom, NEW_GAME, [{"steps": "", "at": 1, "read": [("ram", R.INIT_RAM, R.INIT_SIZE)]}])[0]["read"][0]
    init = rom.init(0, R.INIT_SIZE)
    diff = [i for i in range(R.INIT_SIZE) if ram[i] != init[i]]
    other = [i for i in diff if i not in REROLLED]
    print(f"[block] $FF1000 +{R.INIT_SIZE:#x}: {R.INIT_SIZE - len(diff)}/{R.INIT_SIZE} bytes equal ROM 0x{R.INIT:X}; "
          f"differing only in the player's rerolled abilities: {not other}"
          + (f" (also {', '.join(f'+{i:#x}' for i in other[:10])})" if other else ""))

    print("ALL OK" if not other else f"{len(other)} unexpected byte(s)")
    sys.exit(1 if other else 0)


if __name__ == "__main__":
    main()
