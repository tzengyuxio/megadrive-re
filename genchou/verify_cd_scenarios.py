#!/usr/bin/env python3
"""Verify the Mega-CD scenario data (cd.load + rom.LAYOUTS["C"]) against the game in Genesis Plus GX: pick each
of the 5 menu scenarios and, on the first screen (何人でプレイしますか), compare PRG-RAM at Layout.ram (block A) and
Layout.ram + b_ram (block B) with the disc data; then start a one-player game with the default house and compare
the family block the game copies to Layout.ram + family_ram with that house's block. The persons, countries,
houses and women decoded from the RAM must equal the disc decoding.

What the loader changes: slot 69 of scenario 4 (1185) is emptied, as on the cartridge, and block B +0x516 is set
to the menu scenario number (the disc has the cartridge's numbers there: 0, 0, 1, 2, 3).

Usage: .venv/bin/python genchou/verify_cd_scenarios.py [--image IMAGE]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import cd
import rom as R
from gpgx import Emu
from verify_cd_faces import menu_state

SCENARIO_AT = 0x516                     # block B: the scenario number, written by the loader
TO_TURN = "c" * 6                       # 1 player, default house: Yes, no wars / battles shown, ... first turn


def main() -> None:
    ap = argparse.ArgumentParser(description="Mega-CD 版劇本資料的模擬器驗證")
    ap.add_argument("--image", default=cd.DEFAULT_IMAGE)
    args = ap.parse_args()
    img = cd.load(args.image)
    L = R.layout(img)
    failed = 0
    with Emu(args.image) as emu:
        start = menu_state(emu)
        for n in range(cd.SCENARIO_COUNT):
            emu.load(start)
            emu.tap("c", hold=60, after=100)
            for _ in range(n):
                emu.tap("down", hold=20, after=60)              # longer holds repeat
            emu.tap("c", hold=60, after=300)
            ram = emu.prg_ram()
            a = bytearray(R.block_a(img, n))
            for k in L.loader_empties.get(n, []):
                a[R.PERSONS_AT + L.person_size * k + L.name_len + 7] = 0x80
            b = bytearray(R.block_b(img, n))
            b[SCENARIO_AT] = n
            for c in TO_TURN:
                emu.tap(c, hold=60, after=300)
            fam = R.families(img, n)[0]["address"]
            got = emu.prg_ram()[L.ram + L.family_ram:L.ram + L.family_ram + L.family_size]
            checks = [("block A", ram[L.ram:L.ram + L.a_size], a), ("block B", ram[L.ram + L.b_ram:][:L.b_size], b),
                      ("family", got, img[fam:fam + L.family_size])]
            diffs = [f"{name} {sum(x != y for x, y in zip(g, w))}/{len(w)}" for name, g, w in checks if g != w]
            # the same decoders on the RAM image
            ram_img = bytearray(img)
            pa, pb = R.be32(img, L.scenario_a + 4 * n), R.be32(img, L.scenario_b + 4 * n)
            ram_img[pa:pa + L.a_size] = ram[L.ram:L.ram + L.a_size]
            ram_img[pb:pb + L.b_size] = ram[L.ram + L.b_ram:L.ram + L.b_ram + L.b_size]
            ram_img = bytes(ram_img)
            same = all(f(ram_img, n) == f(img, n) for f in (R.persons, R.countries, R.houses, R.women))
            failed += bool(diffs) or not same
            print(f"scenario {n} ({R.year(img, n)}): " + ("; ".join(diffs) if diffs else
                  f"blocks identical ({L.a_size} + {L.b_size} + family {L.family_size} bytes)")
                  + f"; decoded persons/countries/houses/women {'equal' if same else 'DIFFER'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
