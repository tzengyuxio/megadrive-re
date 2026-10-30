#!/usr/bin/env python3
"""portrait-sheet/1 manifest of the 500 persons' faces (needs export.py's output first).

Usage: .venv/bin/python sgz5/sheet_manifest.py
then:  .venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py \
           sgz5/output/portrait-sheet/sgz5/sheet.json sgz5/output/portrait-sheet/sgz5/out

Person n uses face n (output/faces/NNN_姓名.png, 40x48); persons whose faces are pixel-identical share one cell
(`names`, as the ROM spells them), in person order (the game's surname stroke order). The faces
extra_500-535 are used by no person and left out. Stats: the base 武力 智力 政治 魅力 (persons.csv, without items), only on cells of one person.
"""
import csv
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "sgz5"
STATS = ["武力", "智力", "政治", "魅力"]


def main() -> None:
    src = os.path.join(HERE, "output")
    out = os.path.join(src, "portrait-sheet", SLUG)
    os.makedirs(os.path.join(out, "faces"), exist_ok=True)
    with open(os.path.join(src, "persons.csv"), encoding="utf-8-sig") as f:
        persons = list(csv.DictReader(f))
    cells = {}  # face pixels -> cell, in person order
    for p in persons:
        im = Image.open(os.path.join(src, "faces", f"{p['頭像']}_{p['姓名']}.png")).convert("RGB")
        c = cells.setdefault(im.tobytes(), {"face": f"faces/{p['頭像']}.png", "names": [], "stats": [], "im": im})
        c["names"].append(p["姓名"])
        c["stats"].append([int(p[s]) for s in STATS])
    chars = []
    for c in cells.values():
        c.pop("im").save(os.path.join(out, c["face"]))
        ch = {"face": c["face"], "names": c["names"]}
        if len(c["names"]) == 1:
            ch["stats"] = c["stats"][0]
        chars.append(ch)
    manifest = {"format": "portrait-sheet/1", "slug": SLUG, "game": "三國志V", "title_font": "lanyang-semibold",
                "title": "武將頭像", "platform": "SKOB　Mega Drive", "theme": "paper", "stats": STATS,
                "characters": chars}
    with open(os.path.join(out, "sheet.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"{len(chars)} faces ({len(persons)} persons) -> {out}")


if __name__ == "__main__":
    main()
