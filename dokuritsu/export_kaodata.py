#!/usr/bin/env python3
"""Export MD Liberty or Death as a kaodata dataset (liberty-md, format kaodata/1), laid out as liberty-sfc.

All faces use one 16-colour palette (FACE_PALETTE, MAME's MD colour levels). Portraits 0-173 (KOEI LZ, three
pointer tables); a portrait's face code is its number ("code" 0000-00AD). Composite faces (code bit 15 set, $EC82):
bits 10-11 = type = variant; part p (slots in the drawing order 4, 0, 1, 2, 3) takes variant (code >> PART_BITS[p])
& 3 and writes whole 8x8 cells of the 40x48 face, so every item is a 40x48 canvas with 255 outside the cells the
part writes. Characters are the 250 persons with the English names of the ROM ("given surname"); no reading, no
nameZh (no other version's dataset has one). Portraits 125-173 belong to no person: they get the groups of
liberty-pc98 / -dos in the same order (大陸會議 22, 英國 22, 傳令 2, 海軍 2, 傭兵 1) and, where the ROM's event
person table has one (rom.event_persons), the name.

Usage: .venv/bin/python dokuritsu/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import (
    DEFAULT_ROM,
    EVENT_FIRST_PORTRAIT,
    FACE_H,
    FACE_W,
    PART_BITS,
    PART_ORDER,
    PORTRAIT_COUNT,
    TYPE_COUNT,
    Rom,
    md_rgb,
    packed_pixels,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
PART_LABELS = {4: "下 2 列", 0: "上 4 列", 1: "第 3 列", 2: "第 4 列", 3: "第 5 列"}   # tile rows each part writes
GROUPS = [("大陸會議", 22), ("英國", 22), ("傳令", 2), ("海軍", 2), ("傭兵", 1)]   # portraits 125-173, in order


def slot_id(p: int) -> str:
    return f"part{p}"


def part_cells(rom: Rom, t: int, p: int) -> list[tuple[int, int]]:
    """(source tile in the variant, face cell) pairs that part p of type t writes ($EC82)."""
    _, first, count = rom.part(t, p)
    if (t, p) == (0, 0):
        return [(k, first + k) for k in range(count - 5)] + [(20, 20), (24, 24)]
    return [(k, first + k) for k in range(count)]


def part_image(rom: Rom, t: int, p: int, v: int) -> bytes:
    w, _ = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * CANVAS[1])
    src = rom.part_variant(t, p, v)
    for s, cell in part_cells(rom, t, p):
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for i, c in enumerate(packed_pixels(src[32 * s:32 * s + 32], 1, 1)):
            out[(cy + i // 8) * w + cx + i % 8] = c
    return bytes(out)


def code_parts(code: int) -> tuple[int, list[int]]:
    return code >> 10 & 3, [code >> PART_BITS[p] & 3 for p in PART_ORDER]


def portrait_groups(rom: Rom) -> dict[int, dict]:
    """Portrait number -> {group, name?} for the portraits no person uses."""
    names = {e["portrait"]: e["name"] for e in rom.event_persons() if e["name"]}
    out, n = {}, EVENT_FIRST_PORTRAIT
    for group, count in GROUPS:
        for _ in range(count):
            out[n] = {"group": group, **({"name": names[n]} if n in names else {})}
            n += 1
    return out


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int = 0) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = []
    for t in range(TYPE_COUNT):
        parts = {slot_id(p): {"items": [add(part_image(rom, t, p, v)) for v in range(4)]} for p in PART_ORDER}
        variants.append({"id": str(t), "label": f"型 {t}", "parts": parts})

    groups = portrait_groups(rom)
    portraits = [{"img": add(bytes(rom.face_pixels(n)), blob=1), "code": f"{n:04X}", **groups.get(n, {})}
                 for n in range(PORTRAIT_COUNT)]

    characters = []
    for p in rom.persons():
        code = p["face"]
        ch = {"id": p["id"], "name": p["name"]}
        if code & 0x8000:
            t, parts = code_parts(code)
            ch["face"] = {"variant": t, "parts": parts, "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    meta = {
        "format": kaodata.FORMAT,
        "id": "liberty-md",
        "game": "LIBERTY",
        "platform": "MD",
        "title": {"ja": "独立戦争 Liberty or Death", "zh": "獨立戰爭"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（全員共用，MAME 色階）",
                      "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in map(md_rgb, rom.face_palette())]}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": slot_id(p), "label": PART_LABELS[p]} for p in PART_ORDER],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 liberty-md")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Liberty or Death (USA).zip 或 .md")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    groups = [p["group"] for p in meta["portraits"] if "group" in p]
    print(f"liberty-md: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits "
          f"({', '.join(f'{groups.count(g)} {g}' for g in dict.fromkeys(groups))}), {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
