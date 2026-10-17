#!/usr/bin/env python3
"""Export Mega-CD ウイニングポスト as a kaodata dataset (winning-md, format kaodata/1), laid out as the SFC
version's winning-sfc (superfamicom-re), whose faces it shares colour index for colour index.

Pixels are `palette * 16 + colour`: the dataset palette is the game's 6 face palettes in the SFC order (cd.PALETTES,
96 colours, MAME's MD colour levels; 0-1 for composed faces, 2-5 for portraits, cd.Disc.face_palette_number).
Portraits 0x00-0xCF (ORGKAO.DAT slots 0-207) keep their face code; groups by code range as winning-sfc: 0x00-0x27
調教師, 0x28-0xB5 騎手, 0xB6-0xCE 其他, 0xCF 秘書 (有馬桜子). Composed faces ($18A6E): one variant per type (code
bits 14-12); 4 slots, each with 4 items (the part number, 2 bits of the code): 上半 (cells 0-14 of sheet face n),
下半 (cells 15-29), 零件A / 零件B (the type's two runs of cells, cd.Disc.part_cells); items are 40x48 canvases,
255 outside their cells.

Characters (ids as in winning-sfc): trainers 1000-1029, jockeys 2000-2049 (jockeys 20-69) and 2100-2119
(jockeys 0-19; the 10 foreign ones named "Ｐ・モトリー"), owners 3000-3039 (owner 40, the player, has no face).

The platform is MD (kaodata has no Mega-CD platform); the source input is the Track 01 file.

Usage: .venv/bin/python winning/export_kaodata.py --out <dir> [--image IMAGE]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import cd
import kaodata

CANVAS = (cd.FACE_W * 8, cd.FACE_H * 8)
SLOTS = [("top", "上半"), ("bottom", "下半"), ("part_a", "零件A"), ("part_b", "零件B")]


def portrait_group(code: int) -> str:
    if code < 0x28:
        return "調教師"
    if code <= 0xB5:
        return "騎手"
    return "秘書" if code == cd.SECRETARY_FACE else "其他"


def cells_image(face: bytes, cells: list[int], pal: int) -> bytes:
    """40x48 image: the cells of a sheet face, other cells transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for cell in cells:
        px = cd.decode_tile(face[32 * cell:32 * cell + 32])
        cx, cy = cell % cd.FACE_W * 8, cell // cd.FACE_W * 8
        for j, v in enumerate(px):
            out[(cy + j // 8) * w + cx + j % 8] = pal * 16 + v
    return bytes(out)


def characters(disc: cd.Disc) -> list[dict]:
    out = []
    for t in disc.trainers():
        out.append({"id": 1000 + t["index"], "name": t["surname"] + t["given"], "face": {"portrait": t["face"]}})
    for j in disc.jockeys():
        if j["index"] < 10:         # foreign jockeys: initial + half-width surname whose long vowel is '-'
            name = j["given"] + "・" + j["surname"].replace("-", "ー")
        else:
            name = j["surname"] + j["given"]
        cid = 2000 + j["index"] - 20 if j["index"] >= 20 else 2100 + j["index"]
        out.append({"id": cid, "name": name, "face": {"portrait": j["face"]}})
    for o in disc.owners()[:40]:
        f = cd.composite_fields(o["face"])
        out.append({"id": 3000 + o["index"], "name": o["surname"] + o["given"],
                    "face": {"variant": f["type"], "parts": f["parts"], "code": f"{o['face']:04X}"}})
    return sorted(out, key=lambda c: c["id"])


def build(image: str) -> tuple[dict, list[bytes]]:
    disc = cd.Disc(image)
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = []
    for t in range(cd.TYPES):
        pal = 0 if t < 4 else 1
        cells = disc.part_cells(t)
        parts = {SLOTS[s][0]: {"items": [add(cells_image(disc.sheet_face(t, v), cells[s], pal), 0) for v in range(4)]}
                 for s in range(4)}
        variants.append({"id": str(t), "label": f"類型 {t}", "parts": parts})

    portraits = []
    for code in range(cd.PORTRAIT_COUNT):
        pal = disc.face_palette_number(code)
        p = {"img": add(bytes(pal * 16 + v for v in cd.tiles_pixels(disc.portrait_bytes(code))), 1),
             "code": f"{code:02X}", "group": portrait_group(code)}
        if code == cd.SECRETARY_FACE:
            p["name"] = "有馬桜子"
        portraits.append(p)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for n in range(len(cd.PALETTES)) for r, g, b in map(cd.md_rgb, disc.palette(n))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "winning-md",
        "game": "WINNING",
        "platform": "MD",
        "title": {"ja": "ウイニングポスト", "zh": "賽馬大亨"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": disc.track01, "sha1": disc.sha1}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像 6 組調色盤 SMAIN.PRG $4EEE4–$4EFA4（色號＝組 × 16 ＋ 色；組 0–1 組合臉、"
                      "2–5 頭像，順序同 SFC 版）", "colors": colors}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": i, "label": label} for i, label in SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters(disc),
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 winning-md")
    ap.add_argument("--image", default=cd.DEFAULT_IMAGE, help="roms/megacd/ 的 7z 或 .cue")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.image)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    comp = [c for c in chars if "variant" in c["face"]]
    print(f"winning-md: {len(chars)} characters ({len(chars) - len(comp)} portrait, {len(comp)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
