#!/usr/bin/env python3
"""Verify the Mega-CD scenario images against the game in Genesis Plus GX: pick each of the 4 scenarios and, at
何人でプレイしますか, compare the work RAM (PRG-RAM cd.RAM, 0x7476 bytes: the cartridge's $FF0000-$FF7475) with
SAVEDAT1-4.DAT; the loader changes one byte for 1582 and 1583, +0x72A5 |= 0x40, as the cartridge's does for 1582.

Usage: .venv/bin/python haouden/verify_cd_scenarios.py [--image IMAGE]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import cd
from gpgx import Emu
from verify_cd_faces import pick_scenario, scenario_list


def main() -> None:
    ap = argparse.ArgumentParser(description="覇王伝 Mega-CD 版劇本資料的模擬器驗證")
    ap.add_argument("--image", default=cd.DEFAULT_IMAGE)
    args = ap.parse_args()
    disc = cd.Disc(args.image)
    failed = 0
    with Emu(args.image) as emu:
        scenario_list(emu)
        menu = emu.save()
        for sc in range(cd.SCENARIO_COUNT):
            emu.load(menu)
            pick_scenario(emu, sc)
            want = bytearray(disc.image(sc))
            if sc >= 2:
                want[0x72A5] |= 0x40
            got = emu.prg_ram()[cd.RAM:cd.RAM + len(want)]
            diff = sum(a != b for a, b in zip(got, want))
            failed += bool(diff)
            print(f"{cd.SCENARIO_YEARS[sc]} ({cd.SCENARIO_FILES[sc]}): "
                  + (f"{diff}/{len(want)} bytes differ" if diff else f"{len(want)} bytes identical")
                  + f"; {len(disc.scenario_persons(sc))} persons, {len(disc.future_persons(sc))} later")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
