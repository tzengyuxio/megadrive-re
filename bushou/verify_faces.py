#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette / face_rgb against the game (MAME, about 5 minutes).

Scenario 1, 織田信長: after the last "すべてよろしいですか" Yes the province screen of 尾張 shows Nobunaga's face,
copied to VRAM tile 0x300 (bytes 0x6000, 960 bytes) with CRAM palette 3. The face code comes from Nobunaga's
general record in RAM ($FF27C2 + 40 * 119 + 28). A savestate is taken just before that Yes and, for every
dedicated face 0-203 and every composite code a general uses, the code is written to RAM and the state replayed
(tools/replay.py). The VRAM tiles and palette 3 must equal the ROM decoding, and the 40x48 face in the screenshot
must equal rom.Rom.face_rgb pixel for pixel, except that colour 0 is transparent on screen and shows the
background behind the face (BACKGROUND); an unpatched run must show face 25 (Nobunaga's own).

Usage: .venv/bin/python bushou/verify_faces.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from export_kaodata import distinct_characters
from replay import replay
from rom import (
    DEFAULT_ROM,
    FACE_BYTES,
    FACE_PALETTE,
    GENERAL_SIZE,
    GENERAL_START,
    PORTRAIT_COUNT,
    RAM_BASE,
    Rom,
    be16,
    is_composite,
)

BOOT = ("w3500 start:10 w300 start:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w300 up:6 w60 c:10 w300 "
        "c:10 w300 left:10 w200 c:10 w200")  # ... daimyo map -> 織田 Yes -> 他国の合戦 見ない -> すべてよろしいですか
STEPS, AT = "left:10 w300", 320                # Yes -> province screen of 尾張
NOBUNAGA = 119
FACE_RAM = 0xFF0000 + RAM_BASE + GENERAL_START + GENERAL_SIZE * NOBUNAGA + 28
FACE_VRAM, FACE_CRAM = 0x300 * 32, 3 * 32
NOBUNAGA_FACE = 25
BACKGROUND = (87, 0, 0)  # what colour-0 (transparent) face pixels show on the province screen


def find_face(shot: str, rgb: list) -> tuple[int, int] | None:
    im = Image.open(shot).convert("RGB")
    px = im.load()
    for y in range(im.height - 47):
        for x in range(im.width - 39):
            if px[x, y] == rgb[0] and all(px[x + i % 40, y + i // 40] == c for i, c in enumerate(rgb)):
                return x, y
    return None


def screen_face(shot: str, x: int, y: int) -> list:
    im = Image.open(shot).convert("RGB")
    return list(im.crop((x, y, x + 40, y + 48)).get_flattened_data())


def screen_ok(rom: Rom, shot: str, pos: tuple[int, int], code: int) -> bool:
    got = screen_face(shot, *pos)
    return all(g == (BACKGROUND if v == 0 else w) for g, v, w in zip(got, rom.face_pixels(code), rom.face_rgb(code)))


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼（專屬頭像與組合臉）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th face")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    assert be16(rom.general_record(0, NOBUNAGA), 28) == NOBUNAGA_FACE
    composite = sorted({c["face_code"] for c in distinct_characters(rom) if is_composite(c["face_code"])})
    portraits = list(range(PORTRAIT_COUNT))
    if args.quick:
        portraits, composite = portraits[::8], composite[::8]
    read = [("vram", FACE_VRAM, FACE_BYTES), ("cram", FACE_CRAM, 32)]
    runs = [{"steps": STEPS, "at": AT, "shot": True, "read": read}]
    runs += [{"ram": [(FACE_RAM, c.to_bytes(2, "big"))], "steps": STEPS, "at": AT, "shot": True, "read": read}
             for c in portraits + composite]
    res = replay(args.rom, BOOT, runs)
    pal = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    errors = 0
    pos = find_face(res[0]["shot"], rom.face_rgb(NOBUNAGA_FACE))
    natural = res[0]["read"] == [rom.face_tiles(NOBUNAGA_FACE), pal] and pos is not None
    print(f"[natural] 織田信長 shows face {NOBUNAGA_FACE} (VRAM, CRAM, screenshot at {pos}): "
          + ("OK" if natural else "NG"))
    errors += not natural
    shown = dict(zip(portraits + composite, res[1:]))
    for label, codes in (("portraits", portraits), ("composite", composite)):
        bad = [c for c in codes if shown[c]["read"] != [rom.face_tiles(c), pal]]
        bad_px = [c for c in codes if pos is None or not screen_ok(rom, shown[c]["shot"], pos, c)]
        errors += len(bad) + len(bad_px)
        print(f"[{label}] {len(codes) - len(bad)}/{len(codes)}: VRAM tiles and CRAM palette 3 match the ROM"
              + (f" (NG {[hex(c) for c in bad[:20]]})" if bad else ""))
        print(f"[{label}] {len(codes) - len(bad_px)}/{len(codes)}: screenshot 40x48 equals rom.Rom.face_rgb (colour 0 = background)"
              + (f" (NG {[hex(c) for c in bad_px[:20]]})" if bad_px else ""))
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
