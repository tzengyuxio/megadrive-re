#!/usr/bin/env python3
"""Export MD 三國志V (China, unlicensed): persons, the 7 scenarios' persons / cities / forces / relations, items,
string tables, portraits, the font sheet and the ruler-select map.

Usage: .venv/bin/python sgz5/export.py [--out DIR]   # default sgz5/output/

Writes persons.csv, person_scenarios.csv, cities.csv, forces.csv, relations.csv, items.csv, strings.csv, faces/
(000-499 by person, extra_500-535), font.png (7 banks x 240 glyphs), map.png and map_labelled.png.
"""
import argparse
import csv
import json
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    BANK_COUNT,
    BANK_SIZE,
    FACE_COUNT,
    FACE_H,
    FACE_W,
    HELD_ITEMS,
    NO_RANK,
    PERSON_COUNT,
    SCENARIO_COUNT,
    SCENARIOS,
    STATUS,
    TABLES,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/STHeiti Medium.ttc"  # any font with CJK; PIL default if missing
SAN5 = os.path.expanduser("~/works/kaodata/data/san5pk-dos/dataset.json")  # external: 三國志V DOS 中文版


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"已匯出 {len(rows)} 筆 → {path}")


def person_rows(rom: Rom) -> list[dict]:
    san5 = {}
    if os.path.exists(SAN5):
        with open(SAN5, encoding="utf-8") as f:
            san5 = {c["name"]: c["id"] for c in json.load(f)["characters"]}
    rows = []
    for p in rom.persons(0):
        b = p["base"]
        rows.append({"Id": p["id"], "姓名": p["name"], "武力": b[0], "智力": b[1], "政治": b[2], "魅力": b[3],
                     "+A(hex)": f"{p['a']:04X}", "頭像": f"{p['id']:03d}",
                     "[EXT]三國志V_DOS_id": san5.get(p["name"], "")})
    return rows


def person_scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        cities = rom.city_names()
        items = rom.strings("items")
        for p in rom.persons(s):
            a = p["abilities"]
            rows.append({"劇本": s + 1, "Id": p["id"], "姓名": p["name"], "身份": STATUS.get(p["status"], p["status"]),
                         "所在": cities[p["city"]] if p["city"] < len(cities) else p["city"],
                         "武力": a[0], "智力": a[1], "政治": a[2], "魅力": a[3], "經驗值": p["exp"], "威名": p["fame"],
                         "忠誠": p["loyalty"], "將軍職碼": "" if p["rank"] == NO_RANK else p["rank"],
                         "寶物": "、".join(items[k] for k in p["items"])})
    return rows


def city_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        names, rulers = rom.names(), rom.rulers(s)
        for c in rom.cities(s):
            ruler = rulers[c["force"]] if c["force"] < len(rulers) else 0xFFFF
            rows.append({"劇本": s + 1, "Id": c["id"], "城名": c["name"],
                         "勢力": "" if c["force"] == 0xFF else c["force"],
                         "君主": names[ruler] if ruler < PERSON_COUNT else "",
                         "太守": names[c["governor"]] if c["governor"] < PERSON_COUNT else "",
                         "農": c["farm"], "商": c["trade"], "人口": c["population"], "民忠": c["support"],
                         "治水度": c["flood"], "士兵數": c["soldiers"], "訓練": c["training"], "士氣": c["morale"],
                         "+16": c["limit16"], "+18": c["limit18"]})
    return rows


def force_rows(rom: Rom) -> list[dict]:
    rows = []
    names = rom.names()
    for s in range(SCENARIO_COUNT):
        owners = rom.city_owners(s)
        for f in rom.forces(s):
            if f["ruler"] >= PERSON_COUNT:
                continue
            rows.append({"劇本": s + 1, "Id": f["id"], "君主": names[f["ruler"]], "♡": f["heart"], "金": f["gold"],
                         "糧": f["food"], "+C": f["unk_c"], "城數": sum(o == f["id"] for o in owners)})
    return rows


def relation_rows(rom: Rom) -> list[dict]:
    rows = []
    names = rom.names()
    for s in range(SCENARIO_COUNT):
        rel, rulers = rom.relations(s), rom.rulers(s)
        for i, ri in enumerate(rulers):
            for j, rj in enumerate(rulers):
                if i != j and ri < PERSON_COUNT and rj < PERSON_COUNT:
                    rows.append({"劇本": s + 1, "勢力": names[ri], "對象": names[rj], "值": rel[20 * i + j]})
    return rows


def item_rows(rom: Rom) -> list[dict]:
    names, items = rom.names(), rom.strings("items")
    rows = []
    for k, item in enumerate(items):
        row = {"Id": k, "名稱": item}
        if k < HELD_ITEMS:
            b = rom.item_bonus(k)
            row.update({"武力+": b[0], "智力+": b[1], "政治+": b[2], "魅力+": b[3]})
            for s in range(SCENARIO_COUNT):
                o = rom.item_owners(s)[k]
                row[f"劇本{s + 1}持有"] = names[o] if o < PERSON_COUNT else ""
        rows.append(row)
    return rows


def string_rows(rom: Rom) -> list[dict]:
    return [{"表": t, "Id": k, "文字": v} for t in TABLES if t != "names" for k, v in enumerate(rom.strings(t))]


def font_sheet(rom: Rom, path: str) -> None:
    im = Image.new("L", (16 * 17, BANK_COUNT * 15 * 17), 255)
    for b in range(BANK_COUNT):
        for i in range(BANK_SIZE):
            px = rom.glyph_pixels(b, i)
            x0, y0 = (i % 16) * 17, (b * 15 + i // 16) * 17
            for y in range(16):
                for x in range(16):
                    if px[y][x]:
                        im.putpixel((x0 + x, y0 + y), 0)
    im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(path)


def font(size: int):
    try:
        return ImageFont.truetype(LABEL_FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def map_images(rom: Rom, out: str) -> None:
    w, h, px = rom.map_rgb()
    im = Image.new("RGB", (w, h))
    im.putdata(px)
    im.resize((w * 2, h * 2), Image.NEAREST).save(os.path.join(out, "map.png"))
    big = im.resize((w * 4, h * 4), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    f = font(16)
    for k, ((cx, cy), name) in enumerate(zip(rom.map_nodes(), rom.city_names())):
        x, y = 32 * cx + 32, 32 * cy + 32  # the node is the 2x2 cells from (cx, cy)
        dr.rectangle([x - 32, y - 32, x + 32, y + 32], outline="red", width=2)
        dr.text((x + 34, y), f"{k} {name}", fill="white", anchor="lm", font=f, stroke_width=2, stroke_fill="black")
    big.save(os.path.join(out, "map_labelled.png"))


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 MD 三國志V（中國盜版）資料")
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom()
    os.makedirs(os.path.join(args.out, "faces"), exist_ok=True)
    for rows, fn in ((person_rows(rom), "persons"), (person_scenario_rows(rom), "person_scenarios"),
                     (city_rows(rom), "cities"), (force_rows(rom), "forces"), (relation_rows(rom), "relations"),
                     (item_rows(rom), "items"), (string_rows(rom), "strings")):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    names = rom.names()
    for n in range(FACE_COUNT):
        im = Image.new("RGB", (FACE_W, FACE_H))
        im.putdata(rom.face_rgb(n))
        fn = f"{n:03d}_{names[n]}.png" if n < PERSON_COUNT else f"extra_{n:03d}.png"
        im.save(os.path.join(args.out, "faces", fn))
    font_sheet(rom, os.path.join(args.out, "font.png"))
    map_images(rom, args.out)
    print(f"劇本 {len(SCENARIOS)} 個；頭像 {FACE_COUNT} 張；字型表、選君主地圖 → {args.out}")


if __name__ == "__main__":
    main()
