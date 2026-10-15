#!/usr/bin/env python3
"""Verify the scenario decoding (rom.ram_image) against the game: start each of the 3 scenarios in MAME, dump the RAM
when the loader at $3E28 returns (Layout.loader_rts: $3FF8, Chinese ROM $4024) and compare it with what
rom.ram_image says, table by table. The Chinese version takes the same key presses.

Usage: .venv/bin/python retsuden/verify_scenarios.py [--rom ROM]   # Japanese (default) or Chinese ROM
"""
import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from drive import events_lua, schedule
from mame import run

TITLE = "w900 start:10 w120 c:10 w200 c:10 w200 c:10 w200 c:10 w200 c:10 w200 "  # → settings, シナリオ column active
SETTINGS = "c:10 w200 c:10 w200 c:10 w300 c:10 w300 c:10 w300 w300 c:10 w300 w1500 c:10 w300 c:10 w300"


def boot(n: int) -> str:
    """Key presses from power-on to the first turn of scenario n (0-2), default ruler."""
    return TITLE + "down:6 w30 " * n + SETTINGS


def main() -> None:
    ap = argparse.ArgumentParser(description="劇本資料的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.load(args.rom)
    failed = 0
    for n, year in enumerate(R.SCENARIO_YEARS):
        events, end = schedule(boot(n).split())
        with tempfile.TemporaryDirectory() as tmp:
            hook = f'local done=false\non_exec(0x{R.layout(rom).loader_rts:X}, function() if not done then dump("{tmp}/s"); done=true end end)\n'
            run(args.rom, hook + events_lua(events, f"{tmp}/end", end, False), debug=True)
            with open(f"{tmp}/s.ram", "rb") as fh:
                ram = fh.read()
        diffs = []
        for (addr, want), (_, _, _, field) in zip(R.ram_image(rom, n).items(), R.SCENARIO_TABLES):
            got = ram[addr & 0xFFFF:(addr & 0xFFFF) + len(want)]
            d = [i for i in range(len(want)) if got[i] != want[i]]
            if d:
                diffs.append(f"{field} {len(d)}")
        tables = len(R.SCENARIO_TABLES)
        failed += bool(diffs)
        print(f"{year}年: {tables - len(diffs)}/{tables} tables identical" + (f"; differ: {', '.join(diffs)}" if diffs else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
