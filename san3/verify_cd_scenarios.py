#!/usr/bin/env python3
"""Verify the Mega-CD scenario blocks (SINARIO.DAT, cd.Disc) against the game in Genesis Plus GX: pick each of the
7 menu scenarios and, at 何人でプレイしますか, compare the work RAM records the loader builds (the cartridge's
$FF0000 layout at PRG-RAM cd.RAM) with the decoding, as verify_scenarios.py does on the cartridge: persons
($1562 + 30 i: soldiers, rank, loyalty, province and the static record's bytes) and provinces ($07C4 + 52 k: the
fields that don't depend on the factions). Factions, the header, the extra table and item owners are not decoded
on the CD.

Usage: .venv/bin/python san3/verify_cd_scenarios.py [--image IMAGE]
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
from verify_cd_faces import pick_scenario, scenario_list


def check(disc: cd.Disc, n: int, ram: bytes) -> dict[str, tuple[int, int]]:
    def b(a: int) -> int:
        return ram[a]

    def w(a: int) -> int:
        return R.be16(ram, a)

    ok, persons, statics = 0, disc.scenario_persons(n), disc.persons()
    for sp in persons:
        a, st, rank = 0x1562 + 30 * sp["id"], statics[sp["id"]], sp["rank_byte"]
        want = [sp["soldiers"], st["raw"][2], st["raw"][3], st["flags4"], 0 if rank == 0xFF else rank & 0x7F,
                st["affinity"], st["duty"], sp["loyalty"], sp["province"]]
        got = [w(a + 2), b(a + 6), b(a + 7), b(a + 0xA), b(a + 0xC), b(a + 0xD), b(a + 0xE), b(a + 0xF), b(a + 0x10)]
        ok += got == want
    res = {"persons": (ok, len(persons))}
    ok, provs = 0, disc.scenario_provinces(n)
    for p in provs:
        a = 0x07C4 + 52 * p["id"]
        got = [w(a + 0xA), w(a + 0xC) * 100, w(a + 0xE), R.be32(ram, a + 0x10), b(a + 0x15), b(a + 0x16),
               b(a + 0x17), b(a + 0x1C), b(a + 0x1E), b(a + 0x1F), w(a + 0x20), b(a + 0x22), b(a + 0x23), w(a + 0x24),
               w(a + 0x26), w(a + 0x28), b(a + 0x2B), b(a + 0x2C), b(a + 0x2D)]
        want = [p["w1"], p["population"], p["gold"], p["food"], p["b9"], p["b10"], p["b11"], p["develop"], p["b13"],
                p["flood"], p["commerce"], p["tax"], p["loyalty"], p["w19"], p["w21"], p["w23"], p["b25"], p["b26"],
                p["b27"]]
        ok += got == want
    res["provinces"] = (ok, len(provs))
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description="三國志III Mega-CD 版劇本資料的模擬器驗證")
    ap.add_argument("--image", default=cd.DEFAULT_IMAGE)
    args = ap.parse_args()
    disc = cd.Disc(args.image)
    all_ok = True
    with Emu(args.image) as emu:
        scenario_list(emu)
        menu = emu.save()
        for n in range(cd.SCENARIO_COUNT):
            emu.load(menu)
            pick_scenario(emu, n)
            res = check(disc, n, emu.prg_ram()[cd.RAM:])
            all_ok &= all(a == k for a, k in res.values())
            print(f"scenario {n}: " + "  ".join(f"{k} {a}/{t}" for k, (a, t) in res.items())
                  + f"  ({len(disc.in_play(n))} persons in play)")
    print("OK" if all_ok else "MISMATCH")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
