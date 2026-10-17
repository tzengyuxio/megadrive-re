#!/usr/bin/env python3
"""Export MD 蒼き狼と白き牝鹿・元朝秘史 as a kaodata dataset (genchou-md, format kaodata/1): the Japanese version by
default (the other genchou datasets are Japanese); the USA Genghis Khan II with --rom.

Pixels are the colour numbers 0-15 of palette line 1 (rom.FACE_PALETTE, MAME's MD colour levels); every face of
the game uses it. Composed faces ($73FE): one variant per head (56 = group * 7 + type, group = code bits 12-14).
The game builds a face from 5 parts of the head (eyes, nose, mouth, top, body); each part has 2 versions chosen
by one bit of the face code, and the parts are runs of whole tiles of the 5x6-tile face, so every slot has two
items (40x48 canvases, 255 outside the part's tiles). The slot order is the game's copy order (top, body, eyes,
nose, mouth), so later parts cover earlier ones as in VRAM. Portraits 0-96 (0-56 men, 57-96 women = woman face
code + 0x39).

Characters: the scenario persons and the family blocks distinct by (name, face code) get ids 0-; the women of the
4 scenarios (Japanese: block B of each scenario; USA: one table of 20) distinct the same way get ids 1000-; the
family blocks' children distinct by (name, face code) get ids 2000-, as in the other genchou datasets. Japanese
names written only in kana get a reading (hiragana, ・ → space, as genchou-sfc); names with kanji and the USA's
English names have none. The Japanese version's nameZh comes from data/name_zh.json (by character id; null for
5 children only in the MD version, who get none), taken from kaodata's genchou-pc98/x68/pc88/fc (from KOEI's Chinese
DOS version, typos corrected) by the Japanese names; the USA version has none. Women's portraits no character uses
(the USA version keeps 20 of the women; the Japanese one uses every portrait) get group 女性, without a name.

The Japanese dataset also carries the Mega-CD version (cd.py, `addedIn: "CD"`, kaodata docs/data-format.md): its 21
new portraits (GH2GRP.DAT slots 57-73 men, 114-117 women; the other slots equal the cartridge's 97) are appended as
portraits 97-117. The CD's persons, family blocks, women and children distinct by (name, face code) that the
cartridge doesn't have get new ids after the cartridge's in each range (men, 1000-, 2000-), in the CD's order; 7
cartridge persons whose composed face the CD replaces with a new portrait keep it and get the portrait as an
expression labelled Mega-CD 版. The CD shows pre-rendered composites (cd.py), equal to the cartridge's parts except
for 4 heads when the nose and body versions differ (one tile): the ones the characters use are appended as
portraits too, the Mega-CD 版 expression of the cartridge characters using them and the face of the CD's own;
other CD characters with composed faces use the cartridge's parts. --no-cd leaves the CD out.

Usage: .venv/bin/python genchou/export_kaodata.py --out <dir> [--rom ROM] [--cd IMAGE | --no-cd]
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import cd
import kaodata
import megacd
import rom as R

CANVAS = (R.FACE_W * 8, R.FACE_H * 8)
HEADS = 56
SLOT_LABELS = {"eyes": "眼", "nose": "鼻", "mouth": "口", "top": "上部", "body": "下部"}
# face group → culture, from the persons' culture field (+19 bits 2-4) of the composed faces (inferred)
FACE_GROUPS = ["蒙古", "中國", "內亞", "印度", "日本", "西歐", "東歐", "伊斯蘭"]
WOMEN_ID = 1000
CHILD_ID = 2000
NAME_ZH = os.path.join(HERE, "data", "name_zh.json")
CD_PORTRAITS = [*cd.NEW_MEN, *cd.NEW_WOMEN]      # appended after the cartridge's portraits
CD_LABEL = "Mega-CD 版"


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


def characters(rom: bytes, scenarios: int = R.SCENARIO_COUNT) -> list[dict]:
    out, seen = [], []
    rows = [p for n in range(scenarios) for p in R.persons(rom, n)]
    rows += [p for n in range(scenarios) for f in R.families(rom, n) for p in f["persons"]]
    for r in rows:
        if (key := (r["name"], r["face"])) not in seen:
            seen.append(key)
            out.append({"id": len(seen) - 1, "name": r["name"], "code": r["face"], "woman": False})
    women = []
    for w in (w for n in range(scenarios) for w in R.women(rom, n)):
        if (key := (w["name"], w["face"])) not in women:
            women.append(key)
            out.append({"id": WOMEN_ID + len(women) - 1, "name": w["name"], "code": w["face"], "woman": True})
    kids = []
    for k in (k for n in range(scenarios) for f in R.families(rom, n) for k in f["children"]):
        if (key := (k["name"], k["face"])) not in kids:
            kids.append(key)
            out.append({"id": CHILD_ID + len(kids) - 1, "name": k["name"], "code": k["face"], "woman": False})
    return out


def cd_characters(found: list[dict], img: bytes) -> tuple[list[dict], dict[int, int]]:
    """The CD's characters the cartridge's (found) don't have, with new ids, and {cartridge id: CD face code} for
    the cartridge persons whose face the CD changes (same name and range, not found by (name, code))."""
    ranges = [(0, WOMEN_ID), (WOMEN_ID, CHILD_ID), (CHILD_ID, 3000)]
    have = {(c["name"], c["code"], c["woman"]) for c in found}
    nxt = [max(c["id"] for c in found if lo <= c["id"] < hi) + 1 for lo, hi in ranges]
    new, changed = [], {}
    for c in characters(img, cd.SCENARIO_COUNT):
        if (c["name"], c["code"], c["woman"]) in have:
            continue
        r = next(i for i, (lo, hi) in enumerate(ranges) if lo <= c["id"] < hi)
        old = [o for o in found if o["name"] == c["name"] and ranges[r][0] <= o["id"] < ranges[r][1]]
        if old:
            assert len(old) == 1 and old[0]["id"] not in changed
            changed[old[0]["id"]] = c["code"]
        else:
            new.append({**c, "id": nxt[r]})
            nxt[r] += 1
    return new, changed


def cd_portrait(n: int) -> int:
    """The dataset portrait of GH2GRP.DAT slot n."""
    if n in CD_PORTRAITS:
        return R.PORTRAIT_COUNT + CD_PORTRAITS.index(n)
    return n if n < cd.NEW_MEN.start else n - cd.NEW_MEN.stop + R.WOMAN_PORTRAIT


def names_zh() -> dict[int, str | None]:
    with open(NAME_ZH, encoding="utf-8") as f:
        return {int(k): v for k, v in json.load(f).items()}


def reading(name: str) -> str | None:
    """Kana-only names -> hiragana ('・' becomes a space); names with kanji or latin letters have none."""
    s = kaodata.hiragana(name).replace("・", " ")
    return s if all("ぁ" <= c <= "ゖ" or c in "ー " for c in s) else None


def build(rom_path: str, cd_path: str | None = None) -> tuple[dict, list[bytes]]:
    rom = R.load(rom_path)
    img = cd.load(cd_path) if cd_path else None
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
    for n in CD_PORTRAITS if img else []:
        code = n if n < cd.WOMAN_PORTRAIT else n - cd.WOMAN_PORTRAIT
        portraits.append({"img": add(bytes(R.tiles_pixels(cd.slot(img, n))), blob=1), "code": f"{code:04X}",
                          "addedIn": "CD"})

    found = characters(rom)
    new, changed = cd_characters(found, img) if img else ([], {})
    # composites the CD shows differently from the cartridge's parts
    redrawn = sorted({c["code"] for c in found + new if c["code"] & 0x8000
                      and cd.face_tiles(img, c["code"]) != R.face_tiles(rom, c["code"])}) if img else []
    for code in redrawn:
        portraits.append({"img": add(bytes(R.tiles_pixels(cd.face_tiles(img, code))), blob=1), "code": f"{code:04X}",
                          "addedIn": "CD"})

    def face(code: int, woman: bool, on_cd: bool) -> dict:
        if on_cd and code in redrawn:
            return {"portrait": R.PORTRAIT_COUNT + len(CD_PORTRAITS) + redrawn.index(code)}
        if code & 0x8000:
            f = R.face_fields(code)
            return {"variant": f["head"], "parts": [f["variants"][k] for k in R.DRAW_ORDER], "code": f"{code:04X}"}
        if on_cd:
            return {"portrait": cd_portrait(cd.face_slot(code, woman))}
        return {"portrait": code + (R.WOMAN_PORTRAIT if woman else 0)}

    chars = []
    zh = names_zh() if R.layout(rom).region == "J" else {}
    if zh:
        assert sorted(zh) == sorted(c["id"] for c in found), "data/name_zh.json does not match the character ids"
    for c in found + new:
        ch = {"id": c["id"], "name": c["name"]}
        if zh.get(c["id"]):
            ch["nameZh"] = zh[c["id"]]
        if (r := reading(c["name"])) is not None:
            ch["reading"] = r
        ch["face"] = face(c["code"], c["woman"], c in new)
        if c["id"] in changed:
            ch["expressions"] = [{**face(changed[c["id"]], c["woman"], True), "label": CD_LABEL}]
        elif c not in new and c["code"] in redrawn:
            ch["expressions"] = [{**face(c["code"], c["woman"], True), "label": CD_LABEL}]
        if c in new:
            ch["addedIn"] = "CD"
        chars.append(ch)
    chars.sort(key=lambda ch: ch["id"])
    used = {c["face"]["portrait"] for c in chars if "portrait" in c["face"]}
    for n in range(R.WOMAN_PORTRAIT, R.PORTRAIT_COUNT):
        if n not in used:
            portraits[n]["group"] = "女性"
    inputs = [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom).hexdigest()}]
    if img:
        track, sha1 = megacd.track01_sha1(cd_path)
        inputs.append({"path": track, "sha1": sha1})

    meta = {
        "format": kaodata.FORMAT,
        "id": "genchou-md",
        "game": "GENCHOU",
        "platform": "MD",
        "title": {"ja": "蒼き狼と白き牝鹿・元朝秘史",
                  "zh": "蒼狼與白鹿・元朝秘史"},
        "source": {"producer": "megadrive-re", "revision": kaodata.revision(REPO),
                   "inputs": inputs},
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
    ap.add_argument("--rom", default=R.DEFAULT_ROM, help="roms/ 的 zip 或 .md（預設日版）")
    ap.add_argument("--cd", default=cd.DEFAULT_IMAGE, help="Mega-CD 映像（roms/megacd/ 的 .7z；只用於日版）")
    ap.add_argument("--no-cd", action="store_true", help="不含 Mega-CD 版")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    japanese = R.layout(R.load(args.rom)).region == "J"
    meta, blobs = build(args.rom, args.cd if japanese and not args.no_cd else None)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    women = [c for c in chars if WOMEN_ID <= c["id"] < CHILD_ID]
    kids = [c for c in chars if c["id"] >= CHILD_ID]
    print(f"genchou-md: {len(chars)} characters ({len(chars) - len(women) - len(kids)} men, {len(women)} women, "
          f"{len(kids)} children; "
          f"{len(chars) - len(mobs)} portrait, {len(mobs)} composite), {len(meta['composite']['variants'])} "
          f"variants, {len(meta['portraits'])} portraits, {len(meta['images'])} images")
    added = [c for c in chars if c.get("addedIn")]
    if added:
        print(f"  Mega-CD: {len(added)} characters ({sum(c['id'] < WOMEN_ID for c in added)} men, "
              f"{sum(WOMEN_ID <= c['id'] < CHILD_ID for c in added)} women, {sum(c['id'] >= CHILD_ID for c in added)} "
              f"children), {sum(1 for p in meta['portraits'] if p.get('addedIn'))} portraits, "
              f"{sum(1 for c in chars if 'expressions' in c)} expressions")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
