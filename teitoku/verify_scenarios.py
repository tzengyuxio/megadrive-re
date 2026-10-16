#!/usr/bin/env python3
"""Verify the scenario decoding against the game: start each of the 9 scenarios in MAME (1 player, 日本軍), dump the
RAM when the loader ($10B46) returns (rom.LOADER_DONE) and compare the initialised data area (rom.DATA_RAM to
rom.DATA_END: ships, bases, fleets, sides, admirals, countries, date) with rom.scenario_image.

Usage: .venv/bin/python teitoku/verify_scenarios.py
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as T
from drive import events_lua, schedule
from mame import run

# title → START twice → 新しくゲームを始める (C) → scenario (down) C → players: up (1) C → 日本軍 C → difficulty C →
# Y/N C (the loader runs here)
TITLE = "w2400 start:20 w200 start:20 w300 c:20 w300 "
SETUP = "up:10 w60 c:20 w300 c:20 w300 c:20 w300 c:20 w600"


def scenario_steps(sc: int) -> str:
    return TITLE + "down:10 w60 " * (sc - 1) + "c:20 w300 " + SETUP


def main() -> None:
    rom = T.Rom()
    failed = 0
    for s in rom.scenarios():
        sc = s["id"]
        events, end = schedule(scenario_steps(sc).split())
        with tempfile.TemporaryDirectory() as tmp:
            hook = (f'local done=false\non_exec(0x{T.LOADER_DONE:X}, function() if not done then '
                    f'dump("{tmp}/s"); done=true end end)\n')
            run(rom.path, hook + events_lua(events, f"{tmp}/end", end, False), debug=True)
            ram = Path(f"{tmp}/s.ram").read_bytes() if os.path.exists(f"{tmp}/s.ram") else b""
        img = rom.scenario_image(sc)
        n = T.DATA_END - T.DATA_RAM
        diff = sum(a != b for a, b in zip(img[T.DATA_RAM:T.DATA_END], ram[T.DATA_RAM:T.DATA_END])) if ram else n
        failed += diff != 0
        print(f"scenario {sc} {s['title']} ({s['date']}): RAM ${T.DATA_RAM:04X}-${T.DATA_END - 1:04X} "
              f"{n - diff}/{n} bytes equal" + ("" if diff == 0 else "  NG"))
    print("ALL OK" if not failed else f"{failed} scenario(s) differ")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
