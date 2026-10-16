#!/usr/bin/env python3
"""Export MD エアーマネジメント 大空に賭ける as a kaodata dataset (air-md, format kaodata/1).

Laid out as air-sfc: 33 whole 40x48 portraits, P00-P07 the aides (MANAGER file, group 部下), P08-P27 the
negotiation partners (PERSON file, group 交涉對象) and P28-P32 the makers' representatives (MAKER file, group 廠商,
name = the maker name). The game names none of the people and keeps no face code, so there are no characters and
no `code`. The MD has 5 face palettes (ROM 0x755D4, CRAM line 3 when drawn); a pixel is palette x 16 + colour,
with each face in the palette the game pairs it with (Rom.default_palette, checked by verify_faces.py). Colour 0
is transparent on the MD; the dataset keeps it as palette colour 0. Maker names are stored half-width with an
ASCII "-" for the long-vowel mark; they are written full-width (NFKC, "-" -> "ー") as in air-sfc.

Usage: .venv/bin/python airmanage/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_H, FACE_PALETTE_COUNT, FACE_W, Rom, md_rgb

CANVAS = (FACE_W * 8, FACE_H * 8)
GROUPS = ["部下", "交涉對象", "廠商"]  # by face kind, as in air-sfc


def full_width(s: str) -> str:
    return unicodedata.normalize("NFKC", s).replace("-", "ー")


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    makers = {m["face_image"]: full_width(m["name"]) for m in rom.makers()}
    images, blob, portraits = [], bytearray(), []
    for n, f in enumerate(rom.faces()):
        images.append([len(blob), *CANVAS])
        blob.extend(16 * f["palette"] + v for row in rom.face_pixels(f["kind"], f["image"]) for v in row)
        pt = {"img": n, "group": GROUPS[f["kind"]]}
        if f["kind"] == 2:
            pt["name"] = makers[f["image"]]
        portraits.append(pt)
    colors = [f"#{r:02x}{g:02x}{b:02x}" for p in range(FACE_PALETTE_COUNT) for r, g, b in map(md_rgb, rom.face_palette(p))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "air-md",
        "game": "AIR",
        "platform": "MD",
        "title": {"ja": "エアーマネジメント 大空に賭ける", "zh": "航空霸業"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像 5 組調色盤（色號＝組 × 16 ＋ 色，MAME 色階）", "colors": colors}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": [],
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 air-md")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Air Management - Oozora ni Kakeru (Japan).zip 或 .md")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    groups = [p["group"] for p in meta["portraits"]]
    print(f"air-md: {len(meta['portraits'])} portraits (" + ", ".join(f"{g} {groups.count(g)}" for g in GROUPS)
          + f"), {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
