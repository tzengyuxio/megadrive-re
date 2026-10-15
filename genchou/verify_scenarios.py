#!/usr/bin/env python3
"""Verify the scenario blocks against the game: pick each of the 3 menu scenarios in MAME, dump the RAM when the
loader ($26250) returns and compare block A ($FF0000), block B ($FF1826), the first family blocks ($FF1592), the
place names ($FF8114) and label positions ($FF1AAA, $FF1ACC) with the ROM; then decode the persons, countries
and houses from the RAM and compare them with the ROM decoding (slot 69 of scenario 4 is emptied by the loader,
the 4th scenario is not in the menu and is checked by forcing D2 = 3).

Usage: .venv/bin/python genchou/verify_scenarios.py [--rom ROM]
"""
import argparse
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

LOADER, LOADER_END = 0x26250, 0x26384
MENU = "w1100 start:10 w200 start:10 w200 c:10 w200"   # → "Which scenario?"


def expected(rom: bytes, n: int) -> list[tuple[str, int, bytes]]:
    a = bytearray(R.block_a(rom, n))
    for k in R.LOADER_EMPTIES.get(n, []):
        a[R.PERSONS_AT + R.PERSON_SIZE * k + 20] = 0x80
    world = n > 0
    fam = R.be32(rom, R.FAMILIES)
    return [("block A", 0x0000, bytes(a)), ("block B", 0x1826, R.block_b(rom, n)),
            ("families", 0x1592, rom[fam:fam + 0x270]),
            ("place names", 0x8114, rom[R.PLACE_NAMES + 0x1EF * world:R.PLACE_NAMES + 0x1EF * (world + 1)]),
            ("label x", 0x1AAA, rom[R.PLACE_X + 0x42 * world:R.PLACE_X + 0x42 * world + 0x21]),
            ("label y", 0x1ACC, rom[R.PLACE_Y + 0x42 * world:R.PLACE_Y + 0x42 * world + 0x21])]


def main() -> None:
    ap = argparse.ArgumentParser(description="劇本資料的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.load(args.rom)
    failed = 0
    for n in range(R.SCENARIO_COUNT):
        pick = "down:10 w40 " * min(n, 2) + "c:10 w300"
        events, end = schedule((MENU + " " + pick).split())
        with tempfile.TemporaryDirectory() as tmp:
            # scenario 4 isn't in the menu: pick scenario 3 and make the loader load 3 instead
            force = f"wr8(REG('SP')+7, {n})" if n == 3 else ""
            hook = (f"local arg=-1\non_exec(0x{LOADER:X}, function() {force}; arg=rd8(REG('SP')+7) end)\n"
                    f"on_exec(0x{LOADER_END:X}, function() if arg=={n} then dump('{tmp}/s') end end)\n")
            run(args.rom, hook + events_lua(events, f"{tmp}/end", end, False), debug=True)
            ram = Path(f"{tmp}/s.ram").read_bytes()
        diffs = [f"{name} {sum(1 for i in range(len(b)) if ram[a + i] != b[i])}/{len(b)}"
                 for name, a, b in expected(rom, n) if ram[a:a + len(b)] != b]
        # the same decoders on the RAM image
        img = bytearray(rom)
        img[R.be32(rom, R.SCENARIO_A + 4 * n):R.be32(rom, R.SCENARIO_A + 4 * n) + R.A_SIZE] = ram[:R.A_SIZE]
        same = (R.persons(bytes(img), n) == R.persons(rom, n) and R.countries(bytes(img), n) == R.countries(rom, n)
                and R.houses(bytes(img), n) == R.houses(rom, n))
        sizes = [len(b) for _, _, b in expected(rom, n)]
        failed += bool(diffs) or not same
        print(f"scenario {n + 1} ({R.year(rom, n)}): " + ("; ".join(diffs) if diffs else
              "blocks identical (" + " + ".join(map(str, sizes)) + " bytes)")
              + f"; decoded persons/countries/houses {'equal' if same else 'DIFFER'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
