#!/usr/bin/env python3
"""Export MD 大航海時代 as a kaodata dataset (koukai-md, format kaodata/1).

Pixels are colour numbers 0-15 of the one face palette (FACE_PALETTE, loaded into palette line 0 by $386F4),
shown with MAME's levels of the MD colour values. Characters: the player, 20 mates, 20 admirals (ids 0-40) and
20 girls (ids 41-60; $8266 mode 2 draws girl k with portrait k + 13). Portraits 0-52 with their face code (the
code the game passes to $8266 mode 1 is the portrait number). Portraits 1-12 belong to no character: the game
draws them with fixed codes (kings, facilities, the old mate, the princess; docs/ROM_FORMAT.md §5.3) and they get
a group, plus a name where the ROM text says who it is. Composite faces ($ACFC): one variant per head (4). The
game copies 5 parts of whole 8x8 tiles into the 960-byte face, in the order bottom, top, eyes, nose, mouth, a
later part overwriting earlier tiles; the code picks one of 4 pages per slot. Every item is a 40 x 48 canvas
with the part's tiles opaque and 255 elsewhere, so layering the slots in that order gives the game's face.
The ROM has no readings, so characters carry no `reading`.

Usage: .venv/bin/python daikoukai/export_kaodata.py --out <dir> [--rom ROM]
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
    COMPOSITE_HEADS,
    COMPOSITE_SLOTS,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    PORTRAIT_COUNT,
    Rom,
    decode_face_code,
    decode_tile,
    is_composite,
    md_rgb,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
PAGES = 4
# Portraits no character uses, drawn with fixed codes (docs/ROM_FORMAT.md §5.3): group, name (None: no ROM text
# says who it is). Kings: the palace code draws portrait port + 1 for ports 0-2 (リスボン, セビリア, イスタンブール),
# whose nations are the first three of the nation table; facilities by the menus and lines they appear with.
FIXED_PORTRAITS = {1: ("国王", "ポルトガル国王"), 2: ("国王", "イスパニア国王"), 3: ("国王", "イスラム国王"),
                   4: ("施設", None), 5: ("施設", "造船所"), 6: ("施設", "交易所"), 7: ("施設", "酒場"),
                   8: ("特殊人物", "老航海士"), 9: ("施設", "港"), 10: ("施設", "王宮"), 11: ("施設", "宿屋"),
                   12: ("特殊人物", "クリス王女")}


def part_image(first: int, raw: bytes) -> bytes:
    """40 x 48 canvas: the part's tiles (from tile `first`, row-major 5 wide) opaque, the rest transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for k in range(len(raw) // 32):
        cell = first + k
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for i, v in enumerate(decode_tile(raw[32 * k:32 * k + 32])):
            out[(cy + i // 8) * w + cx + i % 8] = v
    return bytes(out)


def characters(rom: Rom) -> list[dict]:
    """Everyone with a face: 41 persons (id 0-40), then 20 girls (id 41-60)."""
    out = [{"id": p["id"], "name": p["name"], "role": p["role"], "face_code": p["face"]} for p in rom.persons()]
    out += [{"id": 41 + g["id"], "name": g["name"], "role": "女性", "face_code": g["face"]} for g in rom.girls()]
    return out


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blob = [], bytearray()

    def add(px: bytes) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blob), w, h])
        blob.extend(px)
        return len(images) - 1

    variants = []
    for head in range(COMPOSITE_HEADS):
        parts = {slot: {"items": [add(part_image(*rom.composite_part(head, slot, page))) for page in range(PAGES)]}
                 for slot, _, _ in COMPOSITE_SLOTS}
        variants.append({"id": str(head), "label": f"頭型 {head}", "parts": parts})

    portraits = []
    for n in range(PORTRAIT_COUNT):
        pt = {"img": add(rom.face_pixels(n)), "code": f"{n:04X}"}
        if n in FIXED_PORTRAITS:
            group, name = FIXED_PORTRAITS[n]
            pt["group"] = group
            if name:
                pt["name"] = name
        portraits.append(pt)

    chars = []
    for c in characters(rom):
        code = c["face_code"]
        ch = {"id": c["id"], "name": c["name"]}
        if is_composite(code):
            head, pages = decode_face_code(code)
            ch["face"] = {"variant": head, "parts": pages, "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        chars.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in map(md_rgb, rom.face_palette())]
    meta = {
        "format": kaodata.FORMAT,
        "id": "koukai-md",
        "game": "KOUKAI",
        "platform": "MD",
        "title": {"ja": "大航海時代", "zh": "大航海時代"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（palette line 0，MAME 色階）", "colors": colors}],
        "blobs": ["pixels.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label, _ in COMPOSITE_SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": chars,
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 koukai-md")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Daikoukai Jidai (Japan).zip 或 .md")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"koukai-md: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits "
          f"({sum('group' in p for p in meta['portraits'])} grouped), {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
