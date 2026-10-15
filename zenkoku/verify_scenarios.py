#!/usr/bin/env python3
"""Verify the scenario decoding against the game: pick each of the 4 scenarios in MAME, dump the RAM when the
loader is done (Layout.loader_done, where both branches meet) and compare RAM from $FF0000 to the end of block 2
with rom.scenario_image, plus the daimyo count (Layout.daimyo_count_ram) and the province count ($0D9E).

Usage: .venv/bin/python zenkoku/verify_scenarios.py [--rom ROM]   # Japan (default) or USA ROM
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as Z
from drive import events_lua, schedule
from mame import run
from verify_faces import TITLE


def main() -> None:
    ap = argparse.ArgumentParser(description="劇本資料的模擬器驗證")
    ap.add_argument("--rom", default=Z.DEFAULT_ROM)
    args = ap.parse_args()
    rom = Z.Rom(args.rom)
    failed = 0
    for s in range(Z.SCENARIO_COUNT):
        events, end = schedule((TITLE + "c:10 w200 " + "down:6 w30 " * s + "c:10 w300").split())
        with tempfile.TemporaryDirectory() as tmp:
            hook = (f'local done=false\non_exec(0x{rom.L.loader_done:X}, function() if not done then '
                    f'dump("{tmp}/s"); done=true end end)\n')
            run(args.rom, hook + events_lua(events, f"{tmp}/end", end, False), debug=True)
            ram = Path(f"{tmp}/s.ram").read_bytes()
        img = rom.scenario_image(s)
        diff = sum(a != b for a, b in zip(img, ram))
        daimyo, provinces = int.from_bytes(ram[rom.L.daimyo_count_ram:][:2], "big"), ram[Z.PROVINCE_COUNT_RAM]
        ok = (diff == 0 and daimyo == rom.scenario_daimyo_count(s) and provinces == rom.province_count(s))
        failed += not ok
        print(f"scenario {s + 1} {rom.scenario_titles()[s]}: {len(img) - diff}/{len(img)} bytes equal; "
              f"daimyo {daimyo} (ROM {rom.scenario_daimyo_count(s)}), provinces {provinces} "
              f"(ROM {rom.province_count(s)})" + ("" if ok else "  NG"))
    print("ALL OK" if not failed else f"{failed} scenario(s) differ")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
