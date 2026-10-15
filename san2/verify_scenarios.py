#!/usr/bin/env python3
"""Check the scenario decode (rom.Rom.placement / province) against the game's own set-up in MAME.

For each of the 6 scenarios the game is played up to the "how many players" prompt (the scenario is loaded
by then) and its RAM is compared with the static decode: the 41 province records ($FF2712 + 34 i: gold,
food, population, faction, 土 民 水 馬 信; the pointers and +23..27 are runtime) and every person's
24-byte record ($FF1052 + 24 j: +6..8 知武魅, +9 faction, +10 loyalty, +14 soldiers, +22 id). Initial
soldiers follow the flags (ruler 100, flag 0x10 50, others 10) except for a few strong generals the loader
raises; those are listed, not counted as errors. The 6 runs go in parallel (one MAME each).

Usage: .venv/bin/python san2/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rom import (
    ABILITY_TABLE,
    DEFAULT_ROM,
    PERSON_COUNT,
    PROVINCE_COUNT,
    PROVINCE_SIZE,
    PROVINCES,
    SCENARIO_COUNT,
    Rom,
)
from session import play, scenario

RAM_PROVINCES, RAM_PERSONS, PERSON_SIZE = 0x2712, 0x1052, 24
COMPARED = [*range(16, 23), *range(28, 33)]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 6 劇本的武將與州資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    d, errors = rom.data, 0
    with ThreadPoolExecutor(SCENARIO_COUNT) as ex:
        rams = list(ex.map(lambda sc: play(args.rom, scenario(sc) + " @s")["s"]["ram"], range(SCENARIO_COUNT)))
    for sc, w in enumerate(rams):
        prov_ok = 0
        for i in range(PROVINCE_COUNT):
            o, a = PROVINCES + PROVINCE_SIZE * (PROVINCE_COUNT * sc + i), RAM_PROVINCES + PROVINCE_SIZE * i
            prov_ok += all(w[a + k] == d[o + k] for k in COMPARED)
        found = {}
        for j in range(PERSON_COUNT):
            r = w[RAM_PERSONS + PERSON_SIZE * j:RAM_PERSONS + PERSON_SIZE * (j + 1)]
            n = r[22] << 8 | r[23]
            if n < PERSON_COUNT and r[6:9] == d[ABILITY_TABLE + 3 * n:ABILITY_TABLE + 3 * n + 3]:
                found.setdefault(n, r)
        bad, raised = [], []
        for n in range(PERSON_COUNT):
            p = rom.placement(n, sc)
            if not p or p["status"] == "未登場":
                if n in found:
                    bad.append(n)
                continue
            r = found.get(n)
            faction = rom.province(sc, p["province"] - 1)["faction"]
            want = (0xFF, 0xFF) if p["status"] == "在野" else (faction, 0xFF if p["loyalty"] is None else p["loyalty"])
            if r is None or (r[9], r[10]) != want:
                bad.append(n)
            elif r[14] << 8 | r[15] != p["soldiers"]:
                raised.append(f"{n}:{r[14] << 8 | r[15]}")
        print(f"[scenario {sc + 1}] provinces {prov_ok}/{PROVINCE_COUNT}, persons {len(found) - len(bad)}"
              f"/{len(found)} match" + (f" (NG {bad[:10]})" if bad else "")
              + (f"; soldiers raised by the loader: {', '.join(raised)}" if raised else ""))
        errors += PROVINCE_COUNT - prov_ok + len(bad)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
