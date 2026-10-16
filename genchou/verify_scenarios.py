#!/usr/bin/env python3
"""Verify the scenario blocks against the game: pick each of the 3 menu scenarios in MAME, dump the RAM when the
loader (Layout.loader) returns and compare block A ($FF0000), block B, the first family blocks, the place names and
label positions with the ROM; then decode the persons, countries, houses (and the Japanese version's women, in
block B) from the RAM and compare them with the ROM decoding (slot 69 of scenario 4 is emptied by the loader, the
4th scenario is not in the menu and is checked by forcing D2 = 3).

Usage: .venv/bin/python genchou/verify_scenarios.py [--rom ROM]   # Japanese (default) or USA ROM
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

# → "Which scenario?" (the Japanese title takes Start later)
MENU = {"J": "w1600 start:10 w200 start:10 w200 c:10 w200", "U": "w1100 start:10 w200 start:10 w200 c:10 w200"}


def expected(rom: bytes, n: int) -> list[tuple[str, int, bytes]]:
    L = R.layout(rom)
    a = bytearray(R.block_a(rom, n))
    for k in R.LOADER_EMPTIES.get(n, []):
        a[R.PERSONS_AT + L.person_size * k + L.name_len + 7] = 0x80
    world = n > 0
    fam = R.be32(rom, L.families)
    names = L.place_names + 33 * L.place_len * world
    x = L.place_x + 0x42 * world
    return [("block A", 0x0000, bytes(a)), ("block B", L.b_ram, R.block_b(rom, n)),
            ("families", L.family_ram, rom[fam:fam + 2 * L.family_size]),
            ("place names", L.place_ram, rom[names:names + 33 * L.place_len]),
            ("label x", L.label_ram, rom[x:x + 0x21]),
            ("label y", L.label_ram + 0x22, rom[x + 0x21:x + 0x42])]


def main() -> None:
    ap = argparse.ArgumentParser(description="劇本資料的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.load(args.rom)
    L = R.layout(rom)
    failed = 0
    for n in range(R.SCENARIO_COUNT):
        pick = "down:10 w40 " * min(n, 2) + "c:10 w300"
        events, end = schedule((MENU[L.region] + " " + pick).split())
        with tempfile.TemporaryDirectory() as tmp:
            # scenario 4 isn't in the menu: pick scenario 3 and make the loader load 3 instead
            force = f"wr8(REG('SP')+7, {n})" if n == 3 else ""
            hook = (f"local arg=-1\non_exec(0x{L.loader:X}, function() {force}; arg=rd8(REG('SP')+7) end)\n"
                    f"on_exec(0x{L.loader_end:X}, function() if arg=={n} then dump('{tmp}/s') end end)\n")
            run(args.rom, hook + events_lua(events, f"{tmp}/end", end, False), debug=True)
            ram = Path(f"{tmp}/s.ram").read_bytes()
        diffs = [f"{name} {sum(1 for i in range(len(b)) if ram[a + i] != b[i])}/{len(b)}"
                 for name, a, b in expected(rom, n) if ram[a:a + len(b)] != b]
        # the same decoders on the RAM image
        img = bytearray(rom)
        a, b = R.be32(rom, L.scenario_a + 4 * n), R.be32(rom, L.scenario_b + 4 * n)
        img[a:a + L.a_size] = ram[:L.a_size]
        img[b:b + L.b_size] = ram[L.b_ram:L.b_ram + L.b_size]
        img = bytes(img)
        same = (R.persons(img, n) == R.persons(rom, n) and R.countries(img, n) == R.countries(rom, n)
                and R.houses(img, n) == R.houses(rom, n) and R.women(img, n) == R.women(rom, n))
        sizes = [len(b) for _, _, b in expected(rom, n)]
        failed += bool(diffs) or not same
        print(f"scenario {n + 1} ({R.year(rom, n)}): " + ("; ".join(diffs) if diffs else
              "blocks identical (" + " + ".join(map(str, sizes)) + " bytes)")
              + f"; decoded persons/countries/houses/women {'equal' if same else 'DIFFER'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
