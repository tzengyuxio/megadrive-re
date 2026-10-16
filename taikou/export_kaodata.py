#!/usr/bin/env python3
"""Export MD 太閤立志伝 as a kaodata dataset (taikoh-md, format kaodata/1).

Pixels are colour numbers of the one face palette (16 colours, CRAM line 0 = ROM FACE_PALETTE, MAME's MD colour
levels; verify_faces.py checks it). Colour 0 is transparent on the MD; the dataset keeps it as palette colour 0.
Composite faces (face code bit 15 set, $E266): one variant per face type (12, code bits 8-11). The game's build
order becomes the slots: part 4 (variant = code bits 0-1), then parts 0-3 (bits 6-7, 4-5, 2-3 and again 2-3),
each writing its run of whole 8x8 tiles of the 32x40 face (rom.composite_runs); every item is a 32x40 canvas
with 255 outside the tiles it writes. Parts 2 and 3 take the same variant, as in the game.
Portraits are the 258 LZ faces (portrait n = face code n). Characters are the 716 name table entries (character
id = name id, as the person records refer to them; `name` is "surname given" as in taikoh-sfc).

Usage: .venv/bin/python taikou/export_kaodata.py --out <dir> [--rom ROM]
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
    COMP_ORDER,
    COMP_TYPES,
    COMP_VARIANTS,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    PORTRAIT_COUNT,
    Rom,
    composite_parts,
    is_composite,
    md_rgb,
    tiles_pixels,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
SLOTS = [(f"part{p}", f"部位{p + 1}") for p, _ in COMP_ORDER]


def run_image(first: int, tiles: bytes) -> bytes:
    """32x40 image of a run of tiles starting at tile `first`, other tiles transparent."""
    full = bytearray(FACE_W * FACE_H * 32)
    full[32 * first:32 * first + len(tiles)] = tiles
    px = tiles_pixels(bytes(full))
    w = CANVAS[0]
    cells = range(first, first + len(tiles) // 32)
    return bytes(v if (i // w // 8) * FACE_W + i % w // 8 in cells else kaodata.TRANSPARENT for i, v in enumerate(px))


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
    for t in range(COMP_TYPES):
        parts = {sid: {"items": [add(run_image(*rom.composite_part(t, p, v))) for v in range(COMP_VARIANTS)]}
                 for (p, _), (sid, _) in zip(COMP_ORDER, SLOTS)}
        variants.append({"id": str(t), "label": f"第 {t} 型", "parts": parts})

    portraits = [{"img": add(bytes(rom.face_pixels(n)), blob=1), "code": f"{n:04X}"} for n in range(PORTRAIT_COUNT)]

    characters = []
    for n in rom.names():
        code = n["face"]
        ch = {"id": n["id"], "name": f"{n['surname']} {n['given']}".strip()}
        if is_composite(code):
            t, parts = composite_parts(code)
            ch["face"] = {"variant": t, "parts": [parts[p] for p, _ in COMP_ORDER], "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    meta = {
        "format": kaodata.FORMAT,
        "id": "taikoh-md",
        "game": "TAIKOH",
        "platform": "MD",
        "title": {"ja": "太閤立志伝", "zh": "太閤立志傳"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（全員共用，palette line 0，MAME 色階）",
                      "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in map(md_rgb, rom.face_palette())]}],
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 taikoh-md")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Taikou Risshiden (Japan).zip 或 .md")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"taikoh-md: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
