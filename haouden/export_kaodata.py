#!/usr/bin/env python3
"""Export MD 信長の野望・覇王伝 as a kaodata dataset (nobu5-md, format kaodata/1).

Pixels are colour numbers of the one face palette (16 colours, CRAM line 1). Composed faces ($6F9C): one variant
per face group (0-4 and 6; $6F44 never returns 5). The game's build order becomes the slots: parts 0-4, each
taking variant v of the part's LZ table (index group * 5 + v, v from the code bits) and writing whole 8x8 tiles
from the part's first tile on, later parts overwriting earlier ones; every item is a 40x48 canvas with 255
outside the tiles it writes. Portraits are the 348 LZ streams of the portrait table. Characters are the 817
person ids; the face id is the person id. The ROM has no readings. Portraits no person uses get a group from
EXTRA_PORTRAITS and, where the game shows a label with the face, a name read from that ROM string.

Usage: .venv/bin/python haouden/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from rom import (
    DEFAULT_ROM,
    FACE_GROUPS,
    FACE_H,
    FACE_PART_COUNT,
    FACE_PART_VARIANTS,
    FACE_W,
    PORTRAIT_COUNT,
    Rom,
    decode_tile,
    md_rgb,
    text,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
SLOTS = [(f"part{p}", f"部位{p + 1}") for p in range(FACE_PART_COUNT)]
# portrait -> (group, ROM address of the label shown with it, or None). Face codes 0x36E-0x379 are portraits 0-11
# (0x22E2C: 0x36E + n under "%s家姫君"), 0x392-0x397 / 0x39A-0x3A0 are portraits 327-332 / 333-339;
# portraits 151 and 152 are the faces of person ids 139 and 140, which have no person record.
EXTRA_PORTRAITS = {
    0: ("姫", 0x559F4),  # 0x1BA04: face 0x36E with お市の方 (pointer 0x74BB4)
    **{n: ("姫", None) for n in (1, 2, 3, 4, 6, 7, 8, 9, 10, 11)},
    5: ("姫", 0x549B2),  # 0x1C95C: face 0x373 with 義姫
    **{n: ("不明", None) for n in (151, 152, 327, 328, 329, 331, 332, 333, 334, 335, 338)},  # no reference found
    330: ("事件人物", 0x556A4),  # 0x1C3B6: face 0x395 with ルイス＝フロイス (pointer 0x74BDC)
    336: ("事件人物", 0x545B4),  # 0x17514: face 0x39D with the label 一向衆 (pointer 0x7328A)
    337: ("事件人物", 0x54952),  # 0x18912: face 0x39E, then the label 南蛮商人 (0x1851A)
    339: ("事件人物", None),  # 0x51B6A: face 0x3A0 in the ending (「征夷大将軍…」), no label
}


def tiles_image(first: int, raw: bytes) -> bytes:
    """40x48 image with the tiles of raw written from tile `first` on (clipped to 30 tiles), others transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for k in range(len(raw) // 32):
        t = first + k
        if t >= FACE_W * FACE_H:
            break
        cx, cy = t % FACE_W * 8, t // FACE_W * 8
        for i, v in enumerate(decode_tile(raw[k * 32:k * 32 + 32])):
            out[(cy + i // 8) * w + cx + i % 8] = v
    return bytes(out)


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
    for g in FACE_GROUPS:
        parts = {sid: {"items": [add(tiles_image(rom.face_part_at(g, p), rom.face_part_tiles(g, p, v)))
                                 for v in range(FACE_PART_VARIANTS)]}
                 for p, (sid, _) in enumerate(SLOTS)}
        variants.append({"id": str(g), "label": f"第 {g} 組", "parts": parts})

    portraits = [{"img": add(bytes(rom.face_pixels(tiles=rom.portrait_tiles(n))), blob=1)}
                 for n in range(PORTRAIT_COUNT)]
    for n, (group, label) in EXTRA_PORTRAITS.items():
        portraits[n]["group"] = group
        if label:
            portraits[n]["name"] = text(rom.data[label:label + 40]).strip("\u3000")

    characters = []
    for pid, m in rom.person_master().items():
        r = m["first"]
        ch = {"id": pid, "name": f"{r['surname']} {r['given']}"}
        s = rom.face_source(pid)
        if s[0] == "comp":
            ch["face"] = {"variant": FACE_GROUPS.index(s[1]),
                          "parts": [rom.part_variant(s[2], p) for p in range(FACE_PART_COUNT)], "code": f"{s[2]:04X}"}
        else:
            ch["face"] = {"portrait": s[1]}
        characters.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in (md_rgb(c) for c in rom.face_palette())]
    meta = {
        "format": kaodata.FORMAT,
        "id": "nobu5-md",
        "game": "NOBU5",
        "platform": "MD",
        "title": {"ja": "信長の野望・覇王伝", "zh": "信長之野望・霸王傳"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（CRAM 第 1 列）", "colors": colors}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label in SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 nobu5-md")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"nobu5-md: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
