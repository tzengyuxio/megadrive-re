#!/usr/bin/env python3
"""Verify the scenario decoding against the game: start each of the 4 scenarios in MAME (defaults for level,
players and area, player 1's head office in ロンドン, company name unchanged) and, at the confirmation before
the first turn, compare RAM with Rom: the scenario number $FFA6F6, the start time $FF1FC4, the city records
$FF2050 (89 x 4) and $FF97A4 (89 x 2) (tables A / B, interpolated for scenarios 2 and 3, countries changed by
the world events up to the start), and the four tables memcpy'd at the start ($FF9964 with the type-1 events, $FF25B8, $FF23F0, $FF9858).

Usage: .venv/bin/python airmanage2/verify_scenarios.py [--rom ROM]
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

# power-on → title (START x3) → NEW GAME (C) → scenario menu
SCENARIO_MENU = "w1800 start:10 w300 start:10 w300 start:10 w300 c:10 w300 "
# scenario C, YES C, level C, players C, area (ヨーロッパ) C → head office: the cursor starts at (128, 128);
# left / up / down put it on ロンドン, C C picks it; "会社名を変更しますか？" → right (いいえ) C → "以上の設定でゲームを
# 開始します" (the game state is built by now; the COM players move in the first turn after it)
SETUP = ("c:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w300 left:44 w30 up:84 w30 down:12 w30 c:10 w200 c:10 w300 "
         "right:10 w60 c:10 w300")
# start messages, COM turns; then the world map pans to the head office and the secretary greets the player
GREETING = " c:10 w300" * 5 + " c:10 w600"


def boot(s: int) -> str:
    return SCENARIO_MENU + "down:3 w40 " * s + SETUP


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

        def rd(a: int, n: int, ram: bytes = ram) -> bytes:
            return ram[a - 0xFF0000:a - 0xFF0000 + n]

        city, city2 = rom.scenario_cities(s)
        got = rd(A.RAM_CITY, 4 * A.CITY_COUNT)
        ok_city = sum(got[4 * c:4 * c + 4] == city[4 * c:4 * c + 4] for c in range(A.CITY_COUNT))
        got2 = rd(A.RAM_CITY2, 2 * A.CITY_COUNT)
        ok_city2 = sum(got2[2 * c:2 * c + 2] == city2[2 * c:2 * c + 2] for c in range(A.CITY_COUNT))
        init = rom.init_tables(s)
        ok_init = [a for a, b in init.items() if rd(a, len(b)) == b]
        scen = int.from_bytes(rd(A.RAM_SCENARIO, 2), "big")
        t = int.from_bytes(rd(A.RAM_TIME, 2), "big")
        ok = (scen == s and t == rom.start_time(s) and ok_city == A.CITY_COUNT and ok_city2 == A.CITY_COUNT
              and len(ok_init) == len(init))
        failed += not ok
        print(f"scenario {s + 1} {name} ({year}): $FFA6F6 = {scen}, $FF1FC4 = {t} (expected {rom.start_time(s)}), "
              f"city records {ok_city}/{A.CITY_COUNT}, second records {ok_city2}/{A.CITY_COUNT}, "
              f"start tables {len(ok_init)}/{len(init)}" + ("" if ok else "  NG"))
    print("ALL OK" if not failed else f"{failed} scenario(s) differ")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
