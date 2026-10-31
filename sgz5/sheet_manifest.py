#!/usr/bin/env python3
"""portrait-sheet/1 manifest of every face: the 500 persons' and the 4 unused ones (needs export.py's output first).

Usage: .venv/bin/python sgz5/sheet_manifest.py
then:  .venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py \
           sgz5/output/portrait-sheet/sgz5/sheet.json sgz5/output/portrait-sheet/sgz5/out

One cell per person in person order (the game's surname stroke order), names as the ROM spells them. Person n
uses face n (output/faces/NNN_姓名.png, 40x48); 13 persons have pixel-identical faces (6 faces), so every cell is
tagged: 專屬 for a face only this person has, a quiet 共用N人 for a shared one. Stats: the base 武力 智力 政治 魅力
(persons.csv, without items). After them the faces no person uses, unnamed, tagged 未使用 and marked unseen: only
500-503, since 504-535 are pixel-identical to persons 104-135's faces; slot 536 (a hole in its lower half) is not a
portrait. Both are left out.
"""
import csv
import json
import os
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "sgz5"
STATS = ["武力", "智力", "政治", "魅力"]
EXTRA_END = 504   # faces 500-503 are used by no person (504-535 repeat faces 104-135)


def main() -> None:
    src = os.path.join(HERE, "output")
    out = os.path.join(src, "portrait-sheet", SLUG)
    os.makedirs(os.path.join(out, "faces"), exist_ok=True)
    with open(os.path.join(src, "persons.csv"), encoding="utf-8-sig") as f:
        persons = list(csv.DictReader(f))
    pixels = {}
    for p in persons:
        im = Image.open(os.path.join(src, "faces", f"{p['頭像']}_{p['姓名']}.png")).convert("RGB")
        im.save(os.path.join(out, "faces", f"{p['頭像']}.png"))
        pixels[p["頭像"]] = im.tobytes()
    users = Counter(pixels.values())
    chars = []
    for p in persons:
        n = users[pixels[p["頭像"]]]
        tag = "專屬" if n == 1 else {"text": f"共用{n}人", "style": "quiet"}
        chars.append({"face": f"faces/{p['頭像']}.png", "name": p["姓名"], "tags": [tag],
                      "stats": [int(p[s]) for s in STATS]})
    for n in range(len(persons), EXTRA_END):
        Image.open(os.path.join(src, "faces", f"extra_{n}.png")).save(os.path.join(out, "faces", f"{n}.png"))
        chars.append({"face": f"faces/{n}.png", "tags": [{"text": "未使用", "style": "quiet"}], "unseen": True})
    manifest = {"format": "portrait-sheet/1", "slug": SLUG, "game": "三國志V", "title_font": "lanyang-semibold",
                "title": "武將頭像", "platform": "SKOB　Mega Drive", "theme": "paper", "stats": STATS,
                "characters": chars}
    with open(os.path.join(out, "sheet.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"{len(chars)} cells: {len(persons)} persons ({len(users)} faces), {EXTRA_END - len(persons)} unused -> {out}")


if __name__ == "__main__":
    main()
