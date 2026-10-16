#!/usr/bin/env python3
"""Export MD 大航海時代II as a kaodata dataset (koukai2-md, format kaodata/1).

Pixels are colour numbers of the one face palette (FACE_PALETTE, CRAM line 3: portraits and composite faces alike),
shown with MAME's levels of the MD colour values; colours 16-31 are the grey palette of the hero select
(GREY_PALETTE, CRAM line 2), used only by portraits 128-133.
Characters: persons 0-119 (ids and readings as in koukai2-sfc: the names are the same, the reading is the name in
hiragana), VIPs 120-139 (face = VIP record +7) and women 140-169 (woman k is drawn with portrait 97 + k: $41510
computes it from the record address), as in koukai2-pc98. VIPs and women carry no reading.
Portraits 0-133 with their face code (the portrait number). Portraits 128-133 are heroes 0-5 with colour 14 drawn
as 4, shown in grey for the heroes not chosen on the hero select: they are the heroes' `expressions`. Portraits no
character uses but the story events draw with fixed numbers ($B584 / $E03C) get group 事件人物, and a name where the
event text says who it is (18: 「私がレオン・フェレロです」, 25: 「私の名はエゼキエル」).
Composite faces ($5874, code bit 15): one variant per pack (7, bits 12-14). Slots in the game's copy order: lower
(bits 0-2), upper (bits 9-11), B (bits 6-8) and A (bits 3-5, the A1 and A2 tiles together); every item is a
40 x 48 canvas with the part's tiles opaque and 255 elsewhere.

Usage: .venv/bin/python daikoukai2/export_kaodata.py --out <dir> [--rom ROM]
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
    COMPOSITE_PACKS,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    GREY_PALETTE,
    HEROES,
    PORTRAIT_COUNT,
    SFC_PORTRAITS,
    Rom,
    decode_tile,
    md_rgb,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
SLOTS = [("lower", "下半臉", ["lower"]), ("upper", "上半臉", ["upper"]), ("b", "部件B", ["b"]),
         ("a", "部件A", ["a1", "a2"])]
WOMAN_FACE = 97
VIP_ID, WOMAN_ID = 120, 140
EVENT_PORTRAITS = {18: "レオン・フェレロ", 19: None, 22: None, 25: "エゼキエル", 94: None}


def part_image(rom: Rom, code: int, parts: list[str]) -> bytes:
    """40 x 48 canvas: the tiles the parts copy (in order), the rest transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for part in parts:
        first, raw = rom.composite_part(code, part)
        for k in range(len(raw) // 32):
            cx, cy = (first + k) % FACE_W * 8, (first + k) // FACE_W * 8
            for i, v in enumerate(decode_tile(raw[32 * k:32 * k + 32])):
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
    for t in range(COMPOSITE_PACKS):
        parts = {sid: {"items": [add(part_image(rom, 0x8000 | t << 12 | n << 9 | n << 6 | n << 3 | n, src))
                                 for n in range(8)]} for sid, _, src in SLOTS}
        variants.append({"id": str(t), "label": f"第 {t} 包", "parts": parts})

    portraits = []
    for n in range(PORTRAIT_COUNT):
        grey = 16 if n >= SFC_PORTRAITS else 0
        pt = {"img": add(bytes(grey + v for v in rom.face_pixels(n)), blob=1), "code": f"{n:04X}"}
        if n in EVENT_PORTRAITS:
            pt["group"] = "事件人物"
            if EVENT_PORTRAITS[n]:
                pt["name"] = EVENT_PORTRAITS[n]
        portraits.append(pt)

    def face(code: int) -> dict:
        if code & 0x8000:
            return {"variant": rom.pack_of(code), "parts": [code >> s & 7 for s in (0, 9, 6, 3)], "code": f"{code:04X}"}
        return {"portrait": code}

    characters = []
    for p in rom.persons():
        ch = {"id": p["id"], "name": p["name"], "reading": kaodata.hiragana(p["name"]), "face": face(p["face"])}
        if p["id"] < HEROES:
            ch["expressions"] = [{"portrait": SFC_PORTRAITS + p["id"], "label": "主角選擇畫面（未選）"}]
        characters.append(ch)
    characters += [{"id": VIP_ID + v["id"], "name": v["name"], "face": face(v["face"])} for v in rom.vips()]
    characters += [{"id": WOMAN_ID + w["id"], "name": w["name"], "face": {"portrait": WOMAN_FACE + w["id"]}}
                   for w in rom.women()]

    colors = [f"#{r:02x}{g:02x}{b:02x}" for pal in (rom.face_palette(), rom.face_palette(GREY_PALETTE))
              for r, g, b in map(md_rgb, pal)]
    meta = {
        "format": kaodata.FORMAT,
        "id": "koukai2-md",
        "game": "KOUKAI2",
        "platform": "MD",
        "title": {"ja": "大航海時代II", "zh": "大航海時代II"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（0–15：CRAM line 3；16–31：主角選擇畫面的灰色調色盤；MAME 色階）",
                      "colors": colors}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label, _ in SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 koukai2-md")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Daikoukai Jidai II (Japan).zip 或 .md")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"koukai2-md: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits "
          f"({sum('group' in p for p in meta['portraits'])} grouped), {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
