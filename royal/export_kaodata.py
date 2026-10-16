#!/usr/bin/env python3
"""Export MD ロイヤルブラッド as a kaodata dataset (royal-md, format kaodata/1).

Pixels are colour numbers 0-15 of the one face palette (ROM 0x30C80, CRAM line 3; verify_faces.py checks it).
Every face is a whole 40x48 picture (no composite faces), laid out as in royal-fc: P00-P63 the 64 characters
(face = person number, $6244), P64-P67 the 4 advisers (group 相談役; the adviser screen shows no names) and
P68-P90 the 23 unit faces ($61A6; group 第5部隊, name = the unit name in the ROM). The game keeps no face code, so
portraits have no `code`. Characters are the 64 people of the name table; `name` is the katakana the game shows
(stored half-width) and `reading` the same in hiragana, as in royal-fc. Colour 0 is transparent on the MD (3
pixels of person 15 show the window behind); the dataset keeps them as palette colour 0.

Usage: .venv/bin/python royal/export_kaodata.py --out <dir> [--rom ROM]
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
from rom import ADVISER_FIRST, DEFAULT_ROM, FACE_COUNT, FACE_H, FACE_PALETTE, FACE_W, UNIT_COUNT, Rom

CANVAS = (FACE_W * 8, FACE_H * 8)
FACES = [(n, False) for n in range(FACE_COUNT)] + [(n, True) for n in range(UNIT_COUNT)]  # portrait -> (face, unit)


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    units = rom.units()
    images, blob, portraits = [], bytearray(), []
    for n, (f, unit) in enumerate(FACES):
        images.append([len(blob), *CANVAS])
        blob.extend(rom.face_pixels(f, unit))
        portraits.append({"img": n, "group": "第5部隊", "name": units[f]["name"]} if unit
                         else {"img": n, "group": "相談役"} if f >= ADVISER_FIRST else {"img": n})

    characters = []
    for i in range(ADVISER_FIRST):
        name = rom.person_name(i)
        characters.append({"id": i, "name": name, "reading": kaodata.hiragana(name), "face": {"portrait": i}})
    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in rom.palette(FACE_PALETTE)]
    meta = {
        "format": kaodata.FORMAT,
        "id": "royal-md",
        "game": "ROYAL",
        "platform": "MD",
        "title": {"ja": "ロイヤルブラッド", "zh": "魔法皇冠"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（palette line 3，MAME 色階）", "colors": colors}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 royal-md")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Royal Blood (Japan).zip 或 .md")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    groups = [p.get("group") for p in meta["portraits"]]
    print(f"royal-md: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits "
          f"({groups.count('相談役')} 相談役, {groups.count('第5部隊')} 第5部隊), {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
