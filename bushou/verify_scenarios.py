#!/usr/bin/env python3
"""Check the scenario decode against the game (MAME, about 15 seconds).

For both scenarios the game is played in MAME (savestate replay tools/replay.py) up to the daimyo selection map,
and RAM $FF1000-$FF5253 (where the game copies the scenario block, memcpy at 0x50BA) is compared byte for byte
with the ROM block that rom.Rom reads provinces, tea, daimyo and generals from. Differing bytes are listed by
record field. The decoded tables are then read back from the RAM copy (general records, province values).

Usage: .venv/bin/python bushou/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import (
    BLOCK_SIZE,
    DAIMYO_SIZE,
    DAIMYO_SLOTS,
    DAIMYO_START,
    DEFAULT_ROM,
    GENERAL_SIZE,
    GENERAL_SLOTS,
    GENERAL_START,
    PROVINCE_COUNT,
    PROVINCE_SIZE,
    PROVINCE_START,
    RAM_BASE,
    SCENARIOS,
    TEA_COUNT,
    TEA_SIZE,
    TEA_START,
    Rom,
    be16,
    be32,
)

BOOT = "w3500 start:10 w300 start:10 w300 c:10 w300"  # title (first start is too early) -> 新しく始める -> scenarios
# scenario s: cursor down s times; mode 入門, level 初級, 1 player -> daimyo selection map
PICK = "c:10 w300 c:10 w300 c:10 w300 up:6 w60 c:10 w300"
RAM = 0xFF0000 + RAM_BASE


def region(k: int) -> str:
    if k < PROVINCE_START:
        return f"header+{k}"
    if k < PROVINCE_START + PROVINCE_SIZE * PROVINCE_COUNT:
        return f"province+{(k - PROVINCE_START) % PROVINCE_SIZE}"
    if k < TEA_START:
        return "next later general"
    if k < TEA_START + TEA_SIZE * TEA_COUNT:
        return f"tea+{(k - TEA_START) % TEA_SIZE}"
    if k < DAIMYO_START:
        return "between tea and daimyo"
    if k < DAIMYO_START + DAIMYO_SIZE * DAIMYO_SLOTS:
        return f"daimyo+{(k - DAIMYO_START) % DAIMYO_SIZE}"
    if k < GENERAL_START:
        return "between daimyo and generals"
    if k < GENERAL_START + GENERAL_SIZE * GENERAL_SLOTS:
        return f"general+{(k - GENERAL_START) % GENERAL_SIZE}"
    return "after generals"


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本資料（國、茶器、大名、武將）與 RAM 一致")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    runs = [{"steps": "down:10 w30 " * s + PICK, "at": 1500, "shot": True, "read": [("ram", RAM, BLOCK_SIZE)]}
            for s in range(len(SCENARIOS))]
    res = replay(args.rom, BOOT, runs)
    errors = 0
    for s in range(len(SCENARIOS)):
        ram = res[s]["read"][0]
        b = rom.block(s)
        block = rom.data[b:b + BLOCK_SIZE]
        diff = [k for k in range(BLOCK_SIZE) if ram[k] != block[k]]
        kinds = Counter(region(k) for k in diff)
        info = rom.scenario_info(s)
        print(f"[scenario {s + 1} {info['name']} {info['year']}.{info['month']}] {BLOCK_SIZE - len(diff)}/{BLOCK_SIZE}"
              f" bytes equal; differing fields: {dict(sorted(kinds.items()))}")
        gslots = sorted({(k - GENERAL_START) // GENERAL_SIZE for k in diff if region(k).startswith("general")})
        p42 = [(be16(block, o), be16(ram, o)) for o in (PROVINCE_START + PROVINCE_SIZE * p + 42 for p in range(3))]
        print(f"  general slots differing: {gslots}; province+42 ROM -> RAM (first 3): {p42}")
        # decoded values read back from the RAM copy
        gens = rom.generals(s)
        g_ok = sum(ram[GENERAL_START + GENERAL_SIZE * i:GENERAL_START + GENERAL_SIZE * (i + 1)]
                   == rom.general_record(s, i) for i in range(len(gens)))
        p_ok = 0
        for p in rom.provinces(s):
            o = PROVINCE_START + PROVINCE_SIZE * p["index"]
            got = (be32(ram, o + 12), be32(ram, o + 16), be32(ram, o + 20), ram[o + 24], be32(ram, o + 26),
                   ram[o + 30], be32(ram, o + 32), ram[o + 36], be16(ram, o + 40), be32(ram, o + 58),
                   be32(ram, o + 62), ram[o + 66], ram[o + 67])
            want = (p["gold"], p["rice"], p["kokudaka"], p["flood"], p["town"], p["culture"], p["tech"],
                    p["people_loyalty"], p["castle"], p["soldiers"], p["guns"], p["training"], p["soldier_loyalty"])
            p_ok += got == want
        print(f"  generals {g_ok}/{len(gens)} records equal, provinces {p_ok}/{PROVINCE_COUNT} values equal;"
              f" screenshot {res[s]['shot']}")
        errors += (g_ok != len(gens)) + (p_ok != PROVINCE_COUNT)
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
