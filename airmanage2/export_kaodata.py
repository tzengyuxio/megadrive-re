#!/usr/bin/env python3
"""Export MD エアーマネジメントII 航空王をめざせ as a kaodata dataset (air2-md, format kaodata/1).

Laid out as air2-sfc: the game names none of its people, so there are portraits only — secretaries (SECRET, 7),
staff (STAFF, 11), country representatives (MAYOR, 5) and the aircraft makers' representatives (MAKER,
descriptors at ROM 0x47C98). The game draws a face from a (kind, image, palette) descriptor: secretaries and
staff get a random palette of their home area's set of 4, country representatives one palette per area, makers
a fixed descriptor. Each SECRET / STAFF / MAYOR image is exported once with palette 26 (the European set; on the
SFC the representatives use 0-3, which are blank on the MD), and every maker descriptor as its own portrait
named after the maker (NFKC, upper case, as in air2-sfc) — except bae's and ヤコブレフ's, which point at the
blank palettes 3 and 2 (the game would draw black silhouettes; neither maker sells an aircraft, so they never
appear), leaving 33 portraits. The 30 face palettes are more than a byte pixel can index, so the dataset palette
holds the palettes the portraits use, in ROM order; pixels are `slot * 16 + colour` (MAME levels). Descriptors
are not face codes, so there is no "code". Each portrait has its kind as group.

Usage: .venv/bin/python airmanage2/export_kaodata.py --out <dir> [--rom ROM]
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
from rom import DEFAULT_ROM, FACE_H, FACE_W, Rom, md_rgb

CANVAS = (FACE_W * 8, FACE_H * 8)
GROUPS = {"SECRET": "秘書", "STAFF": "職員", "MAYOR": "國家代表", "MAKER": "廠商"}


def portrait_faces(rom: Rom) -> list[dict]:
    """Rom.faces() without the descriptors whose palette is blank."""
    return [f for f in rom.faces() if any(rom.face_palette(f["palette"]))]


def maker_name(f: dict) -> str:
    return unicodedata.normalize("NFKC", f["maker_name"]).upper()


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    faces = portrait_faces(rom)
    used = sorted({f["palette"] for f in faces})
    images, blob, portraits = [], bytearray(), []
    for f in faces:
        slot = used.index(f["palette"])
        images.append([len(blob), *CANVAS])
        blob.extend(slot * 16 + v for row in rom.face_pixels(f["kind"], f["image"]) for v in row)
        portrait = {"img": len(images) - 1, "group": GROUPS[f["file"]]}
        if f["file"] == "MAKER":
            portrait["name"] = maker_name(f)
        portraits.append(portrait)
    colors = [f"#{r:02x}{g:02x}{b:02x}" for p in used for r, g, b in map(md_rgb, rom.face_palette(p))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "air2-md",
        "game": "AIR2",
        "platform": "MD",
        "title": {"ja": "エアーマネジメントII 航空王をめざせ", "zh": "航空霸業II"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像用到的調色盤 " + ",".join(map(str, used))
                      + "（色號＝第幾組 × 16 ＋ 色，MAME 色階）", "colors": colors}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": [],
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 air2-md")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Air Management II - Koukuuou o Mezase (Japan).zip 或 .md")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    groups = [p["group"] for p in meta["portraits"]]
    counts = ", ".join(f"{g} {groups.count(g)}" for g in GROUPS.values())
    print(f"air2-md: {len(meta['portraits'])} portraits ({counts}), {len(meta['images'])} images, "
          f"{len(meta['characters'])} characters")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
