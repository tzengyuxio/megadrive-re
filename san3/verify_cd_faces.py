#!/usr/bin/env python3
"""Verify the Mega-CD face decoding (cd.Disc.face_tiles) against the game in Genesis Plus GX (tools/gpgx.py): start
a new game of scenario 0 (黄巾の乱), and for every group of 8 face codes write them into the 8 rulers the ruler
selection screen shows first (the person records in PRG-RAM, which the sub CPU reads in place), pick 1 player and
compare the 8 faces' tiles in VRAM ($5180, 960 bytes apart) with ORGKAO.DAT.

Codes: the 307 plain faces and the 311 composite codes of the table at cd.COMPOSED_CODES, i.e. every slot, and the
persons' composite codes not in the table (劉度's D563), which show the table's first slot.

Usage: .venv/bin/python san3/verify_cd_faces.py [--image IMAGE]
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

RULERS = [135, 86, 375, 68, 144, 99, 139, 119]   # 公孫瓚 韓馥 陶謙 何進 孔融 喬瑁 孔伷 厳白虎, in screen order
FACES_VRAM = 0x5180


def scenario_list(emu: Emu) -> None:
    """Boot (BIOS, opening, title, new game) to the scenario list; the game polls the pad slowly."""
    emu.run(900)
    emu.tap("start")
    emu.run(3600)
    for b in ("start", "start", "c"):              # skip the opening, title, new game
        emu.tap(b, hold=60, after=60)
        emu.run(300)


def pick_scenario(emu: Emu, n: int) -> None:
    """From the scenario list to 何人でプレイしますか of menu scenario n."""
    for _ in range(n):
        emu.tap("down", hold=10, after=60)           # longer holds repeat or skip
    emu.tap("c", hold=60, after=60)
    emu.run(300)


def main() -> None:
    ap = argparse.ArgumentParser(description="三國志III Mega-CD 版頭像解碼的模擬器驗證")
    ap.add_argument("--image", default=cd.DEFAULT_IMAGE)
    args = ap.parse_args()
    disc = cd.Disc(args.image)
    codes = list(range(1, R.FACE_COUNT + 1)) + disc.codes
    codes += sorted({p["face"] for p in disc.persons() if p["face"] & 0x8000} - set(disc.codes))
    bad = []
    with Emu(args.image) as emu:
        scenario_list(emu)
        pick_scenario(emu, 0)
        start = emu.save()
        for k in range(0, len(codes), len(RULERS)):
            group = codes[k:k + len(RULERS)]
            emu.load(start)
            for pid, c in zip(RULERS, group):
                emu.write_prg_ram(cd.SMAIN_AT + cd.PERSONS + R.PERSON_SIZE * pid, c.to_bytes(2, "big"))
            emu.tap("up", hold=60, after=60)            # 1 player
            emu.tap("c", hold=60, after=60)
            emu.run(200)
            vram = emu.vram()
            for i, c in enumerate(group):
                at = FACES_VRAM + R.FACE_BYTES * i
                if vram[at:at + R.FACE_BYTES] != disc.face_tiles(c):
                    bad.append(f"{c:04X}")
    extra = codes[R.FACE_COUNT + len(disc.codes):]
    print(f"faces {len(codes) - len(bad)}/{len(codes)} identical ({R.FACE_COUNT} plain, {len(disc.codes)} composite "
          f"= ORGKAO.DAT's {R.FACE_COUNT + len(disc.codes)} slots; not in the table: "
          f"{', '.join(f'{c:04X}' for c in extra)})" + (f"; NG {bad[:20]}" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
