#!/usr/bin/env python3
"""Check the face decoding against the game (MAME savestate replay).

1551, one player, daimyo selection with 龍造寺隆信 (person id 0x30) under the cursor. For every face id the id
field of his record ($FF0D0E, person +34) is set to that id and C is pressed: the confirmation box builds the face
with $7056 and uploads it to VRAM tile $200. The 960 bytes at VRAM $4000 must equal rom.Rom.face_tiles, and CRAM
line 1 the face palette. Unpatched (id 0x30) is checked first.

Usage: .venv/bin/python haouden/verify_faces.py [--rom ROM] [--quick] [--faces 0,48,0x3A0]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import DEFAULT_ROM, FACE_BYTES, Rom

# title -> 新しく始める -> 1551 -> 1 player -> daimyo selection (cursor on 龍造寺隆信)
BOOT = "w3000 start:10 w600 start:10 w600 c:10 w300 c:10 w900 c:10 w600"
ID_FIELD = 0xFF0C3C + 4 * 44 + 34   # person slot 4 (龍造寺隆信) +34
SELF_ID = 0x30


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像解碼的模擬器驗證")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="只驗證每 20 個頭像碼取 1 個")
    ap.add_argument("--faces", help="只驗證這些頭像碼（逗號分隔，可用 0x）")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    fids = rom.face_ids()
    if args.faces:
        fids = [int(x, 0) for x in args.faces.split(",")]
    elif args.quick:
        fids = fids[::20]
    runs = [{"steps": "c:10 w120", "at": 120, "read": [("vram", 0x4000, FACE_BYTES), ("cram", 32, 32)]}]
    runs += [{"ram": [(ID_FIELD, f.to_bytes(2, "big"))], "steps": "c:10 w120", "at": 120,
              "read": [("vram", 0x4000, FACE_BYTES), ("cram", 32, 32)]} for f in fids]
    results = replay(args.rom, BOOT, runs)
    pal = b"".join(c.to_bytes(2, "big") for c in rom.face_palette())
    base_ok = results[0]["read"][0] == rom.face_tiles(SELF_ID) and results[0]["read"][1] == pal
    print(f"unpatched (face id 0x{SELF_ID:X}): {'OK' if base_ok else 'NG'}")
    bad, bad_pal, kinds = [], 0, {"portrait": [0, 0], "comp": [0, 0]}
    for f, res in zip(fids, results[1:]):
        k = rom.face_source(f)[0]
        kinds[k][1] += 1
        if res["read"][0] == rom.face_tiles(f):
            kinds[k][0] += 1
        else:
            bad.append(f)
        bad_pal += res["read"][1] != pal
    print(f"portraits {kinds['portrait'][0]}/{kinds['portrait'][1]}, composite {kinds['comp'][0]}/{kinds['comp'][1]}"
          f", palette NG {bad_pal}" + (f"; NG {[hex(f) for f in bad[:20]]}" if bad else ""))
    ok = base_ok and not bad and not bad_pal
    print(("ALL OK" if ok else "NG") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
