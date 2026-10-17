#!/usr/bin/env python3
"""Export MD 三國志III as a kaodata dataset (san3-md, format kaodata/1).

Palette: 32 colours = face palette 0 (colours 0-15) and palette 1 (16-31), MAME's MD levels; colour 15 of each
is FACE_COLOUR15 (the game doesn't load it, see rom.py). Plain faces 1-307 are portraits 0-306, their pixels
offset by 16 x palette number (FACE_PAL_NO). Composite faces (face word bit 15, palette 0) are 13 types x 5
parts ($8AA5E): each type is a variant, each part a slot whose items are its stored variants (4, 4, 6, 2, 4),
every item a 40x48 canvas with 255 outside the part's tiles. A character's face is
{variant: type, parts: [variant of part 0-4], code: face word}.

Readings get a space after the family name (data/surnames.tsv; names without a family / given split stay whole).
Portraits no character uses get a group: the 10 event persons named by the table at 0x8AF32 (name pointers) /
0x8AF5A (face codes), and the new rulers / generals the game assigns from 4 ranges ($1D8AE: 8 rulers from face
0xE7 or 0xEF, 30 generals from 0xF7 or 0x115; the first of each pair are the men's faces).

The dataset also carries the Mega-CD version (cd.py, `addedIn: "CD"`, kaodata docs/data-format.md). Its plain
faces equal the cartridge's and its person table differs in 2 records: id 68 賈範 became 何進 (a new character
after the cartridge's ids, with a note; the cartridge's 68 stays) and 劉度 got the composite code D563, which the
CD's code table lacks, so the game shows the table's first face, 800C (an expression labelled Mega-CD 版); D563
itself, drawn with the cartridge's parts, is appended as an unused portrait (group 未使用, with a note). Its
pre-rendered composites equal the cartridge's composites of the same code except 19 of type 11, whose tiles 13 / 18
the CD redrew: these are appended as portraits (before D563) and are the Mega-CD 版 expression of the person using
them. --no-cd leaves the CD out.

Usage: .venv/bin/python san3/export_kaodata.py --out <dir> [--rom ROM] [--cd IMAGE | --no-cd]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import cd
import kaodata
import megacd
from rom import COMPOSITE_TYPE_COUNT, DEFAULT_ROM, FACE_COUNT, FACE_H, FACE_W, PART_VARIANTS, Rom, decode_tile, md_rgb

CANVAS = (FACE_W * 8, FACE_H * 8)
SURNAMES = os.path.join(HERE, "data", "surnames.tsv")
UNSPLIT = {"阿会喃", "金環結", "沙摩可", "朶思王", "董荼奴", "貂蝉"}  # 南蠻 names and 貂蝉: no family / given split
EVENT_NAMES, EVENT_FACES = 0x8AF32, 0x8AF5A  # 10 name pointers and the 10 face codes they go with
EVENT_COUNT = 10
NEW_FACES = [(0xE7, 8, "新君主（男）"), (0xEF, 8, "新君主（女）"), (0xF7, 30, "新武將（男）"),
             (0x115, 30, "新武將（女）")]
SLOTS = [("p0", "上半（推測：頭）"), ("p1", "下半（推測：身）"), ("p2", "目（推測）"), ("p3", "鼻（推測）"),
         ("p4", "口（推測）")]
CD_LABEL = "Mega-CD 版"
CART_LABEL = "卡帶版"         # face label of the characters with a Mega-CD 版 expression


def load_surnames() -> dict[str, str]:
    with open(SURNAMES, encoding="utf-8") as f:
        return dict(line.rstrip("\n").split("\t") for line in f if not line.startswith("#"))


def split_reading(name: str, kana: str, surnames: dict[str, str]) -> str:
    """'あ かいなん' -> a space after the family name's reading (compound family names first)."""
    if name in UNSPLIT:
        return kana
    for k in (2, 1):
        fam = surnames.get(name[:k])
        if fam and kana.startswith(fam) and len(kana) > len(fam):
            return f"{fam} {kana[len(fam):]}"
    return kana


def portrait_groups(rom: Rom) -> dict[int, dict]:
    """Portrait number -> {group, name?} for the event persons and the new rulers / generals."""
    out = {}
    for k in range(EVENT_COUNT):
        name = rom.text(rom.data[rom.ptr(EVENT_NAMES + 4 * k):])
        face = int.from_bytes(rom.data[EVENT_FACES + 2 * k:EVENT_FACES + 2 * k + 2], "big")
        out[face - 1] = {"group": "事件人物", "name": name}
    for first, count, group in NEW_FACES:
        for face in range(first, first + count):
            out[face - 1] = {"group": group}
    return out


def part_image(rom: Rom, t: int, p: int, v: int) -> bytes:
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for cell, raw in rom.composite_part(t, p, v):
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for i, c in enumerate(decode_tile(raw)):
            out[(cy + i // 8) * w + cx + i % 8] = c
    return bytes(out)


def build(rom_path: str, cd_path: str | None = None) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    disc = cd.Disc(cd_path) if cd_path else None
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = []
    for t in range(COMPOSITE_TYPE_COUNT):
        parts = {sid: {"items": [add(part_image(rom, t, p, v), 0) for v in range(PART_VARIANTS[p])]}
                 for p, (sid, _) in enumerate(SLOTS)}
        variants.append({"id": str(t), "label": f"類型 {t}", "parts": parts})

    portraits, groups = [], portrait_groups(rom)
    for n in range(1, FACE_COUNT + 1):
        base = 16 * rom.face_palette_no(n)
        portraits.append({"img": add(bytes(base + v for v in rom.face_pixels(n)), 1), "code": f"{n:04X}",
                          **groups.get(n - 1, {})})

    # the CD's composites that the cartridge's parts don't draw: portraits after the cartridge's
    redrawn = [c for c in disc.codes if disc.face_tiles(c) != rom.face_tiles(c)] if disc else []
    if disc:
        assert all(disc.face_tiles(n) == rom.face_tiles(n) for n in range(1, FACE_COUNT + 1))
    for c in redrawn:
        portraits.append({"img": add(bytes(v for v in Rom.face_pixels(disc, c)), 1), "code": f"{c:04X}",
                          "addedIn": "CD"})

    # CD person codes missing from the CD's table (劉度's D563): drawn with the cartridge's parts, unused
    for q in disc.persons() if disc else []:
        c = q["face"]
        if c & 0x8000 and c not in disc.codes:
            portraits.append({"img": add(bytes(rom.face_pixels(c)), 1), "code": f"{c:04X}", "group": "未使用",
                              "name": q["name"], "addedIn": "CD",
                              "note": f"Mega-CD 版{q['name']}的人物資料改用這張合成臉，但合成臉碼表沒有收這個碼，"
                                      f"遊戲實際顯示 {disc.codes[0]:04X} 的臉"})

    def face_of(face: int, on_cd: bool = False) -> dict:
        if on_cd and face & 0x8000:
            face = disc.codes[disc.face_slot(face) - cd.COMPOSED]      # the code whose slot the CD shows
        if on_cd and face in redrawn:
            return {"portrait": FACE_COUNT + redrawn.index(face)}
        if face & 0x8000:
            return {"variant": rom.composite_type(face), "parts": rom.composite_variants(face), "code": f"{face:04X}"}
        return {"portrait": face - 1}

    characters, surnames = [], load_surnames()
    cd_persons = disc.persons() if disc else []
    for p in rom.persons():
        ch = {"id": p["id"], "name": p["name"],
              "reading": split_reading(p["name"], kaodata.hiragana(p["reading"]), surnames),
              "face": face_of(p["face"])}
        q = cd_persons[p["id"]] if disc else p
        if disc and q["name"] == p["name"] and face_of(q["face"], True) != ch["face"]:
            ch["expressions"] = [{**face_of(q["face"], True), "label": CD_LABEL}]
            ch["face"] = {**ch["face"], "label": CART_LABEL}
        characters.append(ch)
    for q in cd_persons:
        p = characters[q["id"]]
        if q["name"] != p["name"]:
            characters.append({"id": len(characters), "name": q["name"],
                               "reading": split_reading(q["name"], kaodata.hiragana(q["reading"]), surnames),
                               "face": face_of(q["face"], True), "addedIn": "CD",
                               "note": f"Mega-CD 版取代{p['name']}（{p['id']}）"})

    colours = [md_rgb(c) for no in (0, 1) for c in rom.palette(no)]
    inputs = [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]
    if disc:
        track, sha1 = megacd.track01_sha1(cd_path)
        inputs.append({"path": track, "sha1": sha1})
    meta = {
        "format": kaodata.FORMAT,
        "id": "san3-md",
        "game": "SAN3",
        "platform": "MD",
        "title": {"ja": "三國志III", "zh": "三國志III"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": inputs},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤 0（0–15）＋1（16–31）",
                      "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in colours]}],
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 san3-md")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Sangokushi III (Japan).zip 或 .md")
    ap.add_argument("--cd", default=cd.DEFAULT_IMAGE, help="Mega-CD 映像（roms/megacd/ 的 .7z）")
    ap.add_argument("--no-cd", action="store_true", help="不含 Mega-CD 版")
    ap.add_argument("--out", default=os.path.join(HERE, "output", "kaodata", "san3-md"), help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom, None if args.no_cd else args.cd)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"san3-md: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images → {args.out}")
    if not args.no_cd:
        print(f"  Mega-CD: {sum(1 for c in chars if c.get('addedIn'))} characters, "
              f"{sum(1 for p in meta['portraits'] if p.get('addedIn'))} portraits, "
              f"{sum(1 for c in chars if 'expressions' in c)} expressions")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
