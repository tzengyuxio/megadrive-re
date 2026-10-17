#!/usr/bin/env python3
"""Verify the Mega-CD face decoding (cd.face_tiles) against the game in Genesis Plus GX (tools/gpgx.py): for every
face code, write it into Temujin's record of scenario 1 (block A in PRG-RAM, where the sub CPU reads it), start a
new game and compare the 30 tiles the first screen puts in VRAM for the ruler's face (tile $200, as on the
cartridge), CRAM palette line 1 with the palette at Layout.face_palette, and the screenshot: inside the face, the
pixels of one colour number (other than 0, transparent) must all have one screen colour, a different one per CRAM
colour.

Codes: every slot as a person code (0-0x75: 118 portraits, women's slots too; the women's face routine adds 0x4A,
$12ACE) and every composed-face code in the 5 scenarios' persons, family blocks (with children) and women.

Usage: .venv/bin/python genchou/verify_cd_faces.py [--image IMAGE] [--codes 0,40,C620]
"""
import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import cd
import rom as R
from gpgx import Emu
from PIL import Image

SCREEN_X, SCREEN_Y = 16, 8              # the face's top-left pixel on screen
TO_GAME = "c" * 8                       # new game, scenario 1, 1 player, Mongols, no battles shown, ... first turn


def menu_state(emu: Emu) -> bytes:
    """Boot (BIOS, logos, opening text, title) to the main menu (何を行いますか); the game polls the pad slowly."""
    emu.run(900)
    emu.tap("start")
    emu.run(2000)
    for b in "cccc":
        emu.tap(b, after=250)
    emu.run(100)
    for i in range(7):
        emu.tap("start" if i % 2 == 0 else "c", hold=60, after=60)
    emu.run(60)
    return emu.save()


def codes_in_data(img: bytes) -> list[int]:
    out = set()
    for n in range(cd.SCENARIO_COUNT):
        out |= {p["face"] for p in R.persons(img, n)}
        out |= {p["face"] for f in R.families(img, n) for p in f["persons"] + f["children"]}
        out |= {w["face"] for w in R.women(img, n)}
    return sorted(c for c in out if c & 0x8000)


def main() -> None:
    ap = argparse.ArgumentParser(description="Mega-CD 版頭像解碼的模擬器驗證")
    ap.add_argument("--image", default=cd.DEFAULT_IMAGE)
    ap.add_argument("--codes", help="只驗證這些頭像碼（十六進位，逗號分隔）")
    ap.add_argument("--shots", help="把每個頭像碼的畫面存到這個目錄")
    args = ap.parse_args()
    img = cd.load(args.image)
    L = R.layout(img)
    codes = ([int(x, 16) for x in args.codes.split(",")] if args.codes
             else list(range(cd.PORTRAIT_COUNT)) + codes_in_data(img))
    at = R.be32(img, L.scenario_a) + R.PERSONS_AT + L.face_at           # slot 0 of scenario 1's block A
    palette = [R.be16(img, L.face_palette + 2 * i) for i in range(16)]
    bad = []
    tmp = tempfile.TemporaryDirectory()
    with Emu(args.image) as emu:
        start = menu_state(emu)
        for c in codes:
            emu.load(start)
            emu.write_prg_ram(at, c.to_bytes(2, "big"))
            for b in TO_GAME:
                emu.tap(b, hold=60, after=100)
            want = cd.face_tiles(img, c)
            if emu.vram()[0x200 * 32:0x200 * 32 + R.FACE_BYTES] != want:
                bad.append(f"{c:04X} tiles")
            if emu.cram()[16:32] != palette:
                bad.append(f"{c:04X} palette")
            path = os.path.join(args.shots or tmp.name, f"face_{c:04X}.png")
            emu.shot(path)
            shot = Image.open(path).convert("RGB")
            seen = {}
            w = R.FACE_W * 8
            for i, v in enumerate(R.tiles_pixels(want)):
                if v:
                    seen.setdefault(v, set()).add(shot.getpixel((SCREEN_X + i % w, SCREEN_Y + i // w)))
            colours = [next(iter(s)) for s in seen.values()]
            if any(len(s) != 1 for s in seen.values()) or len(set(colours)) != len({palette[v] for v in seen}):
                bad.append(f"{c:04X} screen")
    n_portraits = sum(1 for c in codes if not c & 0x8000)
    print(f"faces {len(codes) - len({b.split()[0] for b in bad})}/{len(codes)} identical "
          f"({n_portraits} slots as portrait codes, {len(codes) - n_portraits} composed codes)")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
