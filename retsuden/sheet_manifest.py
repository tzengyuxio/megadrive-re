#!/usr/bin/env python3
"""portrait-sheet/1 manifest of the 256 portraits (needs export.py's output first).

Usage: .venv/bin/python retsuden/sheet_manifest.py
then:  .venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py \
           retsuden/output/portrait-sheet/retsuden/sheet.json retsuden/output/portrait-sheet/retsuden/out

Person n uses portrait n (output/portraits/P###_姓名.png, 48x64, all different); one cell per person in person
order, names and readings as the Japanese ROM writes them (misspellings kept), tag 君主 for the rulers of any
of the 3 scenarios. Stats are left out: they change from scenario to scenario.
"""
import csv
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "retsuden"


def main() -> None:
    src = os.path.join(HERE, "output")
    out = os.path.join(src, "portrait-sheet", SLUG)
    os.makedirs(os.path.join(out, "faces"), exist_ok=True)
    with open(os.path.join(src, "persons.csv"), encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    persons = {}
    for r in rows:
        p = persons.setdefault(int(r["編號"]), {"name": r["姓名"], "sub": r["讀音"], "ruler": False})
        p["ruler"] |= r["身分"] == "君主"
    chars = []
    for n, p in sorted(persons.items()):
        face = f"faces/{n:03d}.png"
        shutil.copy(os.path.join(src, "portraits", f"P{n:03d}_{p['name']}.png"), os.path.join(out, face))
        c = {"face": face, "name": p["name"], "sub": p["sub"]}
        if p["ruler"]:
            c["tags"] = ["君主"]
        chars.append(c)
    manifest = {"format": "portrait-sheet/1", "slug": SLUG, "game": "三國志列傳", "original": "三国志列伝 乱世の英雄たち",
                "title_font": "lanyang-semibold", "title": "武將頭像", "platform": "SEGA　1991　Mega Drive",
                "theme": {"base": "paper", "name_font": "sourcehan-serif", "data_font": "sourcehan-sans"},
                "characters": chars}
    with open(os.path.join(out, "sheet.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"{len(chars)} faces ({sum('tags' in c for c in chars)} rulers) -> {out}")


if __name__ == "__main__":
    main()
