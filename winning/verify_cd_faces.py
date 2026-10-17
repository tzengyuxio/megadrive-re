#!/usr/bin/env python3
"""Verify the face decoding (cd.Disc.face_bytes, face_palette_number) against the game in Genesis Plus GX
(tools/gpgx.py): start a new game and play the initial setup to the trainer list (お世話になる調教師). Pressing C
there shows the trainer through $18C6A (x, y, face code, VRAM tile, palette line), which loads the face (portrait
$12366 or composed $18A6E) into VRAM tile 0x5D6 and its palette ($18BAC) into CRAM line 3. For every code, stop at
$18C6A, replace the code argument (and clear the last-drawn cache $6423E), and compare VRAM $BAC0 (960 bytes) and
CRAM line 3 with the decoder.

Codes: portraits 0x00-0xCE; composed faces: the 41 owners' codes and, for each type, 4 codes whose 4 parts are
(0,1,2,3) rotated (each slot sees each version, the slots differ). The secretary (0xCF; $18C6A would compose it)
is loaded at boot to VRAM $5600 and shown with CRAM line 0 in her dialogs: checked on one during the setup.

Usage: .venv/bin/python winning/verify_cd_faces.py [--image IMAGE]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import cd
from gpgx import Emu

DRAW_FACE = 0x18C6A            # sub CPU: draw face (x, y, code, tile, palette line); args are longs on the stack
LAST_FACE = 0x6423E            # PRG-RAM: code last loaded by DRAW_FACE (skips the load when equal)
FACE_VRAM = 0x5D6 * 32
FACE_LINE = 3
SECRETARY_VRAM = 0x2B0 * 32
SECRETARY_LINE = 0
KANA = "c w60 left:8 w30 down:8 w30 down:8 w30 down:8 w30 c w200"   # katakana entry: ア, then 決定
SETUP = [  # (button presses, hold)
    ("w900 start w600 w600 w600 start w300 start w300 c w300 c w300 c w300 c w300", 60),  # BIOS, opening, menu
    ("down:8 c w300 c w200 c w200 c w200 c w200 c w200 c w200 c w200", 20),   # ゲームを最初から, 関東, 姓
    ("start w60 c w200 start w60 c w200" + " c w200" * 10, 20),                # 姓, 名, 性別, 年齢, 血液型 …
    (" ".join(["c w200"] * 12), 20),                                           # 呼ばれ方, 4歳馬
    (KANA + " c w200 c w200 c w200", 20),                                      # its name, 3歳馬
    ("c w100 " + KANA + " c w200 c w200 c w200", 20),                         # its name, trainer list
]
SECRETARY_STEP = 4             # after this step the secretary's dialog (3歳馬の名前を…) is on screen


def play(emu: Emu, seq: str, hold: int) -> None:
    for s in seq.split():
        if s.startswith("w"):
            emu.run(int(s[1:]))
        else:
            b, _, h = s.partition(":")
            emu.tap(b, hold=int(h or hold), after=60)


def composite_codes(disc: cd.Disc) -> list[int]:
    out = [o["face"] for o in disc.owners() if o["face"] >= cd.PORTRAIT_COUNT]
    for t in range(cd.TYPES):
        for k in range(4):
            p = [(k + j) % 4 for j in range(4)]
            out.append(0x8000 | t << 12 | p[3] << 8 | p[2] << 4 | p[1] << 2 | p[0])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="ウイニングポスト Mega-CD 版頭像解碼的模擬器驗證")
    ap.add_argument("--image", default=cd.DEFAULT_IMAGE)
    args = ap.parse_args()
    disc = cd.Disc(args.image)
    codes = list(range(cd.SECRETARY_FACE)) + composite_codes(disc)
    bad = []
    with Emu(args.image) as emu:
        for i, (seq, hold) in enumerate(SETUP):
            play(emu, seq, hold)
            if i == SECRETARY_STEP:
                c = cd.SECRETARY_FACE
                pal = disc.palette(disc.face_palette_number(c))
                cram = emu.cram()[16 * SECRETARY_LINE:16 * SECRETARY_LINE + 16]
                if emu.vram()[SECRETARY_VRAM:SECRETARY_VRAM + cd.FACE_BYTES] != disc.face_bytes(c) or cram != pal:
                    bad.append(f"{c:04X}")
        start = emu.save()
        code = [0]

        def swap(e: Emu) -> None:
            sp = e.reg(1, "SP")
            e.write_prg_ram(sp + 14, code[0].to_bytes(2, "big"))     # low word of the 3rd long argument
            e.write_prg_ram(LAST_FACE, b"\xff\xff")

        emu.breakpoint(1, DRAW_FACE, swap)
        for c in codes:
            code[0] = c
            emu.load(start)
            emu.tap("c", hold=20, after=20)
            emu.run(60)
            tiles = emu.vram()[FACE_VRAM:FACE_VRAM + cd.FACE_BYTES]
            cram = emu.cram()[16 * FACE_LINE:16 * FACE_LINE + 16]
            if tiles != disc.face_bytes(c) or cram != disc.palette(disc.face_palette_number(c)):
                bad.append(f"{c:04X}" + ("" if tiles == disc.face_bytes(c) else " tiles")
                           + ("" if cram == disc.palette(disc.face_palette_number(c)) else " palette"))
    n = len(codes) + 1
    print(f"faces {n - len(bad)}/{n} identical (portraits {cd.PORTRAIT_COUNT}, composed {n - cd.PORTRAIT_COUNT}: "
          f"tiles and palette)" + (f"; NG {bad[:20]}" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
