#!/usr/bin/env python3
"""Verify the scenario decoding against the game: for each of the 7 scenarios, boot to the scenario list, set the
scenario number ($FF60E3; the menu starts at 3) when the loader ($924) starts and dump the RAM when it returns
($AAA). Every byte the loader writes is compared with rom.py: 500 person records (+3 擔任 is left out: $188F8
derives it from the abilities), 47 cities, 20 forces, city owners, rulers, item owners, the 20 x 20 relation
table and the start date.

Usage: .venv/bin/python sgz5/verify_scenarios.py
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from drive import events_lua, schedule
from mame import run

TO_LIST = "w900 start:10 w300 a:10 w300 a:10 w300"  # title → 開始遊戲 → scenario list → pick (→ loader)
LOADER, LOADER_END = 0x924, 0xAAA
PERSON_BYTES = [0, 1, 2, 4, 5, 6, 7, 8, 9, 0xA, 0xB, 0xC, 0xD, 0xE, 0xF, 0x10, 0x11, 0x12, 0x15, 0x16, 0x17]
CITY_BYTES = list(range(0x1B))
FORCE_BYTES = [0] + list(range(2, 0x14))


def masked(img: bytes, ram: bytes, base: int, size: int, count: int, fields: list[int]) -> tuple[int, int]:
    """(records whose listed bytes all match, records)."""
    ok = 0
    for k in range(count):
        r = size * k
        ok += all(img[r + f] == ram[base + r + f] for f in fields)
    return ok, count


def main() -> None:
    rom = R.Rom()
    events, end = schedule(TO_LIST.split())
    failed = 0
    for s in range(R.SCENARIO_COUNT):
        with tempfile.TemporaryDirectory() as tmp:
            hook = (f'on_exec(0x{LOADER:X}, function() wr8(0xFF60E3, {s}) end)\n'
                    f'local done=false\non_exec(0x{LOADER_END:X}, function() if not done then dump("{tmp}/s"); '
                    f'done=true; quit() end end)\n')
            run(R.DEFAULT_ROM, hook + events_lua(events, f"{tmp}/end", end + 600, False), debug=True)
            ram = Path(f"{tmp}/s.ram").read_bytes()
        checks = {
            "persons": masked(rom.person_image(s), ram, R.PERSON_RAM, R.PERSON_SIZE, R.PERSON_COUNT, PERSON_BYTES),
            "cities": masked(rom.city_image(s), ram, R.CITY_RAM, R.CITY_SIZE, R.CITY_COUNT, CITY_BYTES),
            "forces": masked(rom.force_image(s), ram, R.FORCE_RAM, R.FORCE_SIZE, R.FORCE_COUNT, FORCE_BYTES),
            "owners": (sum(a == b for a, b in zip(rom.city_owners(s), ram[R.OWNERS_RAM:])), R.CITY_COUNT),
            "rulers": (sum(v == int.from_bytes(ram[R.RULERS_RAM + 2 * k:][:2], "big")
                           for k, v in enumerate(rom.rulers(s))), R.FORCE_COUNT),
            "items": (sum(v == int.from_bytes(ram[R.ITEMS_RAM + 2 * k:][:2], "big")
                          for k, v in enumerate(rom.item_owners(s))), R.HELD_ITEMS),
            "relations": (sum(a == b for a, b in zip(rom.relations(s), ram[R.RELATIONS_RAM:])), 400),
            "date": (int(rom.scenario_date(s) == (int.from_bytes(ram[R.YEAR_RAM:][:2], "big"),
                                                  int.from_bytes(ram[R.YEAR_RAM + 2:][:2], "big"))), 1),
        }
        bad = [k for k, (a, b) in checks.items() if a != b]
        failed += bool(bad)
        print(f"scenario {s + 1} {R.SCENARIOS[s]}: " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in checks.items())
              + ("  NG " + ",".join(bad) if bad else ""))
    print("ALL OK" if not failed else f"{failed} scenario(s) differ")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
