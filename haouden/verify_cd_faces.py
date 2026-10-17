#!/usr/bin/env python3
"""Verify the Mega-CD face decoding (cd.Disc.face_tiles) against the game in Genesis Plus GX (tools/gpgx.py), as
verify_faces.py does on the cartridge: 1551, one player, daimyo selection with 龍造寺隆信 under the cursor; for
every face id the id field of his record (person slot 4 +34, work RAM at PRG-RAM cd.RAM) is set to that id and C
is pressed: the 960 bytes at VRAM $4000 must equal Disc.face_tiles and CRAM line 1 the face palette.

Usage: .venv/bin/python haouden/verify_cd_faces.py [--image IMAGE]
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

ID_FIELD = 0x0C3C + 4 * 44 + 34   # person slot 4 (龍造寺隆信) +34, from the work RAM base
SELF_ID = 0x30


def scenario_list(emu: Emu) -> None:
    """Boot (BIOS, logos, opening, title, 新しく始める) to the scenario list; the game polls the pad slowly."""
    emu.run(900)
    emu.tap("start")
    emu.run(1800)
    for b in ("start", "start", "c"):
        emu.tap(b, hold=60, after=60)
        emu.run(240)


def pick_scenario(emu: Emu, n: int) -> None:
    """From the scenario list to 何人でプレイしますか of scenario n."""
    for _ in range(n):
        emu.tap("down", hold=10, after=60)             # longer holds repeat
    emu.tap("c", hold=60, after=60)
    emu.run(240)


def main() -> None:
    ap = argparse.ArgumentParser(description="覇王伝 Mega-CD 版頭像解碼的模擬器驗證")
    ap.add_argument("--image", default=cd.DEFAULT_IMAGE)
    args = ap.parse_args()
    disc = cd.Disc(args.image)
    fids = disc.face_ids()
    pal = disc.face_palette()
    bad, bad_pal, kinds = [], 0, {"portrait": [0, 0], "comp": [0, 0]}
    with Emu(args.image) as emu:
        scenario_list(emu)
        pick_scenario(emu, 0)
        emu.tap("c", hold=60, after=60)                # 1 player
        emu.run(240)
        start = emu.save()
        emu.tap("c", hold=60, after=60)
        emu.run(60)
        base_ok = emu.vram()[0x4000:0x4000 + R.FACE_BYTES] == disc.face_tiles(SELF_ID) and emu.cram()[16:32] == pal
        print(f"unpatched (face id 0x{SELF_ID:X}): {'OK' if base_ok else 'NG'}")
        for f in fids:
            emu.load(start)
            emu.write_prg_ram(cd.RAM + ID_FIELD, f.to_bytes(2, "big"))
            emu.tap("c", hold=60, after=60)
            emu.run(60)
            k = disc.face_source(f)[0]
            kinds[k][1] += 1
            if emu.vram()[0x4000:0x4000 + R.FACE_BYTES] == disc.face_tiles(f):
                kinds[k][0] += 1
            else:
                bad.append(f)
            bad_pal += emu.cram()[16:32] != pal
    new = sum(1 for f in fids if disc.face_source(f) in [("portrait", n) for n in cd.NEW_PORTRAITS])
    print(f"portraits {kinds['portrait'][0]}/{kinds['portrait'][1]} ({new} new on the CD), composite "
          f"{kinds['comp'][0]}/{kinds['comp'][1]}, palette NG {bad_pal}" + (f"; NG {[hex(f) for f in bad[:20]]}"
                                                                             if bad else ""))
    ok = base_ok and not bad and not bad_pal
    print("ALL OK" if ok else "NG")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
