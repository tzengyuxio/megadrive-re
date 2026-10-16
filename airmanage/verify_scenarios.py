#!/usr/bin/env python3
"""Verify the scenario decoding against the game: start each scenario in MAME (player 1 = MAN at 東京, the
rest COM, defaults for names and level) and, on the main screen, compare RAM with the ROM tables:
RAM_SCENARIO (both scenarios' 22 x 5 words, copied as one table), the city records RAM_CITY +2/+4/+6/+10 of the
chosen scenario, the slot counts RAM_SLOT +2, the players' home cities (RAM_PLAYER +2, player 1 = 東京) and each
player's slots in his home city (RAM_SLOT +4 + 2p) = the scenario's HQ slots.

Usage: .venv/bin/python airmanage/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as A
from drive import events_lua, schedule
from mame import run

# power-on → intro → title (START) → NEW GAME (C) → scenario ("down" for 2) C →
# player select: C makes player 1 MAN, down down C = EXIT → HQ selection (cursor on 東京; the game only tests the
# cursor after it moves: left 10 px, right 20 px snaps it back) C → company name, COM change, level, confirm, opening messages: C each
SCENARIO_SELECT = "w3600 start:10 w800 start:10 w200 start:10 w200 c:10 w200 "
HQ_SELECT = "c:10 w200 c:10 w100 down:10 w100 down:10 w100 c:10 w300 "
MAIN = "left:10 w20 right:20 w20 " + "c:10 w300 " * 6 + "c:10 w600 " + "c:10 w300 " * 4 + "w300"


def boot(s: int) -> str:
    return SCENARIO_SELECT + "down:10 w60 " * s + HQ_SELECT + MAIN


def main() -> None:
    ap = argparse.ArgumentParser(description="劇本資料的模擬器驗證")
    ap.add_argument("--rom", default=A.DEFAULT_ROM)
    args = ap.parse_args()
    rom = A.Rom(args.rom)
    failed = 0
    for s, (name, year) in enumerate(A.SCENARIOS):
        events, end = schedule(boot(s).split())
        with tempfile.TemporaryDirectory() as tmp:
            run(args.rom, events_lua(events, f"{tmp}/end", end, False))
            ram = Path(f"{tmp}/end.ram").read_bytes()

        def w(a: int, ram: bytes = ram) -> int:
            return int.from_bytes(ram[a - 0xFF0000:a - 0xFF0000 + 2], "big")

        words = [w(A.RAM_SCENARIO + 2 * i) for i in range(A.CITY_COUNT * 10)]
        ok_words = sum(a == b for a, b in zip(words, rom.scenario_words(0) + rom.scenario_words(1)))
        recs = rom.city_records(s)
        ok_city = sum(tuple(w(A.RAM_CITY + A.RAM_CITY_SIZE * c + k) for k in (2, 4, 6, 10)) == recs[c]
                      for c in range(A.CITY_COUNT))
        cities = rom.scenario_cities(s)

        def slot(c: int, k: int, ram: bytes = ram) -> int:
            return ram[A.RAM_SLOT - 0xFF0000 + A.RAM_SLOT_SIZE * c + k]

        ok_slots = sum(slot(c, 2) == cities[c]["slots"] for c in range(A.CITY_COUNT))
        homes = [w(A.RAM_PLAYER + A.RAM_PLAYER_SIZE * p + 2) for p in range(4)]
        ok_hq = sum(h < A.CITY_COUNT and slot(h, 4 + 2 * p) == cities[h]["hq_slots"] for p, h in enumerate(homes))
        ok = (ok_words == len(words) and ok_city == A.CITY_COUNT and ok_slots == A.CITY_COUNT and homes[0] == 0
              and ok_hq == 4)
        failed += not ok
        print(f"scenario {s + 1} {name} ({year}): words {ok_words}/{len(words)}, city records {ok_city}/22, "
              f"slots {ok_slots}/22, homes {homes} (player 1 東京), HQ slots {ok_hq}/4"
              + ("" if ok else "  NG"))
    print("ALL OK" if not failed else f"{failed} scenario(s) differ")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
