#!/usr/bin/env python3
"""Export MD Genghis Khan II - Clan of the Gray Wolf as a kaodata dataset (genchou-md, format kaodata/1).

Pixels are the colour numbers 0-15 of palette line 1 (rom.FACE_PALETTE, MAME's MD colour levels); every face of
the game uses it. Composed faces ($73FE): one variant per head (56 = group * 7 + type, group = code bits 12-14).
The game builds a face from 5 parts of the head (eyes, nose, mouth, top, body); each part has 2 versions chosen
by one bit of the face code, and the parts are runs of whole tiles of the 5x6-tile face, so every slot has two
items (40x48 canvases, 255 outside the part's tiles). The slot order is the game's copy order (top, body, eyes,
nose, mouth), so later parts cover earlier ones as in VRAM. Portraits 0-96 (0-56 men, 57-96 women = woman face
code + 0x39).

Characters: the scenario persons and the family blocks distinct by (name, face code) get ids 0-; the 20 women
get ids 1000-; the family blocks' children (face code at +18) distinct by (name, face code) get ids 2000-, as in
the other genchou datasets. The names are English (USA version), so there is no reading and no nameZh. The women's
portraits no character uses (the USA version keeps 20 of the women) get group 女性, without a name.

Usage: .venv/bin/python genchou/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
import rom as R

CANVAS = (R.FACE_W * 8, R.FACE_H * 8)
HEADS = 56
SLOT_LABELS = {"eyes": "眼", "nose": "鼻", "mouth": "口", "top": "上部", "body": "下部"}
# face group → culture, from the persons' culture field (+19 bits 2-4) of the composed faces (inferred)
FACE_GROUPS = ["蒙古", "中國", "內亞", "印度", "日本", "西歐", "東歐", "伊斯蘭"]
WOMEN_ID = 1000
CHILD_ID = 2000


def cells_image(rom: bytes, src: int, cells: list[int]) -> bytes:
    """40x48 image: source tile i drawn at face cell cells[i], other cells transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for i, cell in enumerate(cells):
        d = rom[src + 32 * i:src + 32 * i + 32]
        cx, cy = cell % R.FACE_W * 8, cell // R.FACE_W * 8
        for y in range(8):
            for x in range(8):
                out[(cy + y) * w + cx + x] = d[y * 4 + x // 2] >> (4 if x % 2 == 0 else 0) & 15
    return bytes(out)


def characters(rom: bytes) -> list[dict]:
    out, seen = [], []
    rows = [p for n in range(R.SCENARIO_COUNT) for p in R.persons(rom, n)]
    rows += [p for n in range(R.SCENARIO_COUNT) for f in R.families(rom, n) for p in f["persons"]]
    for r in rows:
        if (key := (r["name"], r["face"])) not in seen:
            seen.append(key)
            out.append({"id": len(seen) - 1, "name": r["name"], "code": r["face"], "woman": False})
    for w in R.women(rom):
        out.append({"id": WOMEN_ID + w["id"], "name": w["name"], "code": w["face"], "woman": True})
    kids = []
    for k in (k for n in range(R.SCENARIO_COUNT) for f in R.families(rom, n) for k in f["children"]):
        if (key := (k["name"], k["face"])) not in kids:
            kids.append(key)
            out.append({"id": CHILD_ID + len(kids) - 1, "name": k["name"], "code": k["face"], "woman": False})
    return out


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = R.load(rom_path)
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int = 0) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    slots = [R.PART_NAMES[k] for k in R.DRAW_ORDER]
    variants = []
    for head in range(HEADS):
        parts = {p["name"]: {"items": [add(cells_image(rom, src, p["cells"])) for src in p["src"]]}
                 for p in R.head_parts(rom, head)}
        kind = head % 7  # types 0-4 are men, 5-6 women (as in the FC version)
        sex = f"男 {kind}" if kind < 5 else f"女 {kind - 5}"
        variants.append({"id": str(head), "label": f"{FACE_GROUPS[head // 7]}(推測)／{sex}",
                         "parts": {s: parts[s] for s in slots}})

    portraits = []
    for n in range(R.PORTRAIT_COUNT):
        code = n if n < R.WOMAN_PORTRAIT else n - R.WOMAN_PORTRAIT
        portraits.append({"img": add(bytes(R.tiles_pixels(R.portrait_tiles(rom, n))), blob=1),
                          "code": f"{code:04X}"})

    chars = []
    for c in characters(rom):
        ch = {"id": c["id"], "name": c["name"]}
        code = c["code"]
        if code & 0x8000:
            f = R.face_fields(code)
            ch["face"] = {"variant": f["head"], "parts": [f["variants"][k] for k in R.DRAW_ORDER],
                          "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code + (R.WOMAN_PORTRAIT if c["woman"] else 0)}
        chars.append(ch)
    used = {c["face"]["portrait"] for c in chars if "portrait" in c["face"]}
    for n in range(R.WOMAN_PORTRAIT, R.PORTRAIT_COUNT):
        if n not in used:
            portraits[n]["group"] = "女性"

    meta = {
        "format": kaodata.FORMAT,
        "id": "genchou-md",
        "game": "GENCHOU",
        "platform": "MD",
        "title": {"ja": "蒼き狼と白き牝鹿・元朝秘史",
                  "zh": "蒼狼與白鹿・元朝秘史"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（palette line 1，MAME 色階）",
                      "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in R.face_palette(rom)]}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": s, "label": SLOT_LABELS[s]} for s in slots],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": chars,
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 genchou-md")
    ap.add_argument("--rom", default=R.DEFAULT_ROM, help="roms/ 的 zip 或 .md")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    women = [c for c in chars if WOMEN_ID <= c["id"] < CHILD_ID]
    kids = [c for c in chars if c["id"] >= CHILD_ID]
    print(f"genchou-md: {len(chars)} characters ({len(chars) - len(women) - len(kids)} men, {len(women)} women, "
          f"{len(kids)} children; "
          f"{len(chars) - len(mobs)} portrait, {len(mobs)} composite), {len(meta['composite']['variants'])} "
          f"variants, {len(meta['portraits'])} portraits, {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
