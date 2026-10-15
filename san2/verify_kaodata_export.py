#!/usr/bin/env python3
"""Independent checks for the san2-md kaodata dataset.

1. Every character and portrait drawn by the spec renderer from the dataset equals the face
   composed directly from ROM tiles (rom.Rom.face_pixels + palette), pixel by pixel.
2. checksums.json matches a recomputation.
3. (MAME) The game draws every face code (the 352 persons' codes and portraits 1-208): from a savestate at
   the ruler pick of scenario 1 (session.MAP), 袁術's face code (person 4, ROM 0x4BB14 + 10 x 4 + 8) is
   patched and C pressed (plus 32 synthetic composite codes: every head with records 0-3 in all slots and
   palettes 0-3, so every composite tile is drawn at least once); his face is drawn from VRAM tiles 0x420-0x43D with CRAM line 2. The screenshot
   must equal the dataset's RGB pixel by pixel (MAME colour levels, rom.LEVELS); the VRAM tiles and
   CRAM line 2 are checked against the ROM too. About 1 minute.

Usage: .venv/bin/python san2/verify_kaodata_export.py --dataset <dir> [--rom ROM] [--no-emulator]
"""
import argparse
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from rom import (
    COMPOSITE_HEADS,
    COMPOSITE_SLOTS,
    DEFAULT_ROM,
    FACE_PALETTES,
    PERSON_SIZE,
    PERSON_TABLE,
    PORTRAIT_COUNT,
    Rom,
)

YUAN_SHU = 4
FACE_VRAM, FACE_LINE = 0x420, 2


def expected(rom: Rom, code: int) -> bytes:
    pal = rom.face_palette_number(code)
    return bytes(pal * 16 + v for v in rom.face_pixels(code))


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> int:
    codes = {p["id"]: p["face"] for p in rom.persons()}
    faces = [(f"ch:{c['id']} {c['name']}", c["face"], codes[c["id"]]) for c in meta["characters"]]
    faces += [(f"pt:{n}", {"portrait": n}, n + 1) for n in range(PORTRAIT_COUNT)]
    errors = 0
    for label, face, code in faces:
        w, h, px = kaodata.compose_display(meta, blobs, face)
        if (w, h) != (40, 48) or px != expected(rom, code):
            print(f"  NG {label}")
            errors += 1
    print(f"[pixels] {len(faces) - errors}/{len(faces)} faces match the ROM tile composition")
    return errors


def check_checksums(meta: dict, blobs: list[bytes], path: str) -> int:
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)
    ok = stored == kaodata.checksums(meta, blobs)
    print(f"[checksums] {'OK' if ok else 'MISMATCH'} ({len(stored['entries'])} entries)")
    return 0 if ok else 1


def find_face(img, rgb: list[tuple[int, int, int]]) -> tuple[int, int] | None:
    w, h = img.size
    px = img.load()
    for y in range(h - 47):
        for x in range(w - 39):
            if all(px[x + i % 40, y + i // 40][:3] == rgb[i] for i in range(0, 40 * 48, 7)):
                return x, y
    return None


def check_emulated(rom: Rom, meta: dict, blobs: list[bytes]) -> int:
    from PIL import Image
    from replay import replay
    from session import MAP  # also puts the repo's tools/ on sys.path
    colors = [tuple(bytes.fromhex(c[1:])) for c in meta["palettes"][0]["colors"]]
    faces = {n + 1: {"portrait": n} for n in range(PORTRAIT_COUNT)}
    for c in meta["characters"]:
        if "variant" in c["face"]:
            faces.setdefault(int(c["face"]["code"], 16), c["face"])
    used = len(faces)
    for head in range(COMPOSITE_HEADS):  # every record of every head in every slot, every palette
        for rec in range(4):
            code = 0x8000 | rec << 13 | head | sum(rec << shift for _, _, shift in COMPOSITE_SLOTS)
            faces.setdefault(code, {"variant": rec * COMPOSITE_HEADS + head, "parts": [rec] * len(COMPOSITE_SLOTS)})
    codes = sorted(faces)
    at = PERSON_TABLE + PERSON_SIZE * YUAN_SHU + 8

    def chunk(cs: list[int]) -> list[dict]:
        return replay(rom.path, MAP, [{"rom": [(at, bytes([c >> 8, c & 255]))], "steps": "c:10 w200", "at": 200,
                                       "shot": True, "read": [("vram", 32 * FACE_VRAM, 960), ("cram", 32 * FACE_LINE, 32)]}
                                      for c in cs])

    parts = [codes[k::6] for k in range(6)]
    with ThreadPoolExecutor(6) as ex:
        results = dict(zip([c for p in parts for c in p], [r for rs in ex.map(chunk, parts) for r in rs]))
    pos, bad = None, []
    for code in codes:
        r = results[code]
        rgb = [colors[v] for v in kaodata.compose_display(meta, blobs, faces[code])[2]]
        img = Image.open(r["shot"]).convert("RGB")
        pos = pos or find_face(img, rgb)
        vram, cram = r["read"]
        pal = rom.face_palette_number(code)
        ok = pos is not None and all(img.getpixel((pos[0] + i % 40, pos[1] + i // 40)) == rgb[i] for i in range(40 * 48))
        ok &= all(vram[32 * i:32 * i + 32] == rom.data[o:o + 32] for i, o in enumerate(rom.face_cells(code)))
        ok &= cram == rom.data[FACE_PALETTES + 32 * pal:FACE_PALETTES + 32 * pal + 32]
        if not ok:
            bad.append(f"{code:04X}")
    for r in results.values():
        shutil.rmtree(os.path.dirname(r["shot"]), ignore_errors=True)
    print(f"[emulator] game screen at {pos}: {len(codes) - len(bad)}/{len(codes)} face codes match"
          f" ({used} used by persons/portraits + {len(codes) - used} synthetic composites)"
          f" (screen pixels, VRAM tiles, CRAM)" + (f" (NG {' '.join(bad[:10])})" if bad else ""))
    return len(bad)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 san2-md kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--no-emulator", action="store_true", help="略過模擬器比對")
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    errors = check_pixels(rom, meta, blobs)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    if not args.no_emulator:
        errors += check_emulated(rom, meta, blobs)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
