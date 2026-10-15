#!/usr/bin/env python3
"""Check the scenario decoding against the game (MAME savestate replay, about 30 seconds).

For each scenario the game is played up to the player-count screen (the loader at $1E2EE has copied the scenario
image to $FF001A and the common block to $FF6F54), RAM $FF0000-$FF7475 is compared byte for byte with
rom.Rom.ram_image, and the persons, castles and daimyo are decoded again from the RAM copy and compared.

Usage: .venv/bin/python haouden/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import COMMON_RAM, COMMON_SIZE, DEFAULT_ROM, SCENARIO_COUNT, SCENARIO_YEARS, Rom

BOOT = "w3000 start:10 w600 start:10 w600 c:10 w300"  # title -> 新しく始める -> scenario menu (cursor on 1551)
END = COMMON_RAM + COMMON_SIZE - 0xFF0000


def picks(sc: int) -> str:
    return "down:10 w30 " * sc + "c:10 w600"


def main() -> None:
    ap = argparse.ArgumentParser(description="劇本資料的模擬器驗證")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    runs = [{"steps": picks(sc), "at": 700, "read": [("ram", 0xFF0000, END)]} for sc in range(SCENARIO_COUNT)]
    results = replay(args.rom, BOOT, runs)
    errors = 0
    for sc, res in enumerate(results):
        ram = res["read"][0]
        want = rom.ram_image(sc)
        diff = [i for i in range(0x1A, END) if ram[i] != want[i]]
        a, b = rom.scenario(sc), rom.scenario(sc, img=ram)
        same = {k: sum(x["raw"] == y["raw"] for x, y in zip(a[k], b[k])) for k in ("persons", "castles", "daimyo")}
        counts = {k: len(a[k]) for k in a}
        ok = not diff and all(same[k] == counts[k] == len(b[k]) for k in a)
        errors += not ok
        print(f"{SCENARIO_YEARS[sc]}: RAM $FF001A-$FF{END - 1:04X} {END - 0x1A - len(diff)}/{END - 0x1A} bytes "
              f"identical; decoded from RAM: persons {same['persons']}/{counts['persons']}, castles "
              f"{same['castles']}/{counts['castles']}, daimyo {same['daimyo']}/{counts['daimyo']}"
              + (f"; first differences at {[hex(0xFF0000 + i) for i in diff[:8]]}" if diff else ""))
    print(("ALL OK" if not errors else f"{errors} scenario(s) differ") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
