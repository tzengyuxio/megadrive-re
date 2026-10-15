#!/usr/bin/env python3
"""Export 三国志列伝 data: persons and cities of the 3 scenarios (CSV, UTF-8-BOM), portraits (PNG), font sheet,
and an .xlsx with every table (needs openpyxl). The Chinese ROM exports to output/cn by default (no 讀音: that
version has no readings).

Usage: .venv/bin/python retsuden/export.py [--rom ROM] [--out DIR] [--scale N]
"""
import argparse
import csv
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rom as R

PERSON_FIELDS = ["hp_max", "hp", "war", "int", "lead", "civil", "military", "virtue", "loyalty", "mobility",
                 "morale", "level", "rank", "soldiers", "p_ba00", "p_bc00", "f000"]
PERSON_HEAD = ["體力上限", "體力", "武力", "知力", "統率力", "文官値", "武官値", "徳", "忠誠度", "機動力", "士氣", "等級",
               "官位碼", "兵力", "UnkBA00", "UnkBC00", "UnkF000"]
CITY_FIELDS = ["city_gold", "city_rice", "city_people", "city_industry", "city_e280", "city_e320", "city_e3c0",
               "city_e460", "city_e500", "city_e5a0"]
CITY_HEAD = ["金", "米", "民(千)", "産業値", "UnkE280", "UnkE320", "UnkE3C0", "UnkE460", "UnkE500", "UnkE5A0"]


def persons(rom: bytes) -> list[list]:
    names, readings, cities = R.names(rom), R.readings(rom), R.city_names(rom)
    rows = []
    for s, year in enumerate(R.SCENARIO_YEARS):
        sc = R.scenario(rom, s)
        rulers = set(sc["faction_ruler"])
        governors = set(sc["city_governor"])
        for i in range(R.N_PERSONS):
            if sc["level"][i] == 0xFF:
                continue
            c = sc["city"][i]
            w = sc["weapons"][i]
            weapons = "、".join(R.weapon_name(rom, slot, v) for slot, v in enumerate(w) if v)
            a1, a2 = R.attack(sc["war"][i], sc["morale"][i], w, rom)
            owner = sc["city_owner"][c - 1] if c else 0xFF
            ruler = names[sc["faction_ruler"][owner]] if owner < R.N_FACTIONS and sc["faction_ruler"][owner] < 256 else ""
            title = "君主" if i in rulers else "太守" if i in governors else ""
            rows.append([year, i, names[i], readings[i], c or "", cities[c - 1] if c else "", ruler, title]
                        + [sc[f][i] for f in PERSON_FIELDS] + [" ".join(map(str, w)), weapons, a1, a2])
    return rows


def city_rows(rom: bytes) -> list[list]:
    names, cities, xy = R.names(rom), R.city_names(rom), R.city_xy(rom)
    rows = []
    for s, year in enumerate(R.SCENARIO_YEARS):
        sc = R.scenario(rom, s)
        for c in range(R.N_CITIES):
            owner = sc["city_owner"][c]
            ruler = sc["faction_ruler"][owner] if owner < R.N_FACTIONS else 0xFFFF
            gov = sc["city_governor"][c]
            rows.append([year, c + 1, cities[c], *xy[c], "" if owner == 0xFF else owner,
                         names[ruler] if ruler < 256 else "", names[gov] if gov < 256 else ""]
                        + [sc[f][c] for f in CITY_FIELDS])
    return rows


def write_csv(path: str, head: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(head)
        w.writerows(rows)


def face_image(rom: bytes, n: int, scale: int = 1, **kw) -> Image.Image:
    pal = [R.md_rgb(w) for w in R.face_palette(rom, n)]
    px = R.face_pixels(rom, n, **kw)
    im = Image.new("RGB", (len(px[0]), len(px)))
    im.putdata([pal[c] for row in px for c in row])
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST) if scale > 1 else im


def map_image(rom: bytes) -> Image.Image:
    px = R.render_nametable(R.strategic_map(rom), R.map_tiles(rom), R.map_palettes(rom))
    im = Image.new("RGB", (len(px[0]), len(px)))
    im.putdata([c for row in px for c in row])
    return im


def label_map(rom: bytes, im: Image.Image) -> Image.Image:
    im = im.copy()
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 18)
    except OSError:
        font = ImageFont.load_default()
    for i, ((x, y), name) in enumerate(zip(R.city_xy(rom), R.city_names(rom)), 1):
        d.text((x + 8, y - 10), f"{i}{name}", fill=(255, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    return im


def font_sheet(rom: bytes) -> Image.Image:
    L = R.layout(rom)
    n, cols = len(R.charset(L.charset)), 32
    im = Image.new("L", (cols * 17, (n + cols - 1) // cols * 17), 40)
    for g in range(n):
        b = rom[L.font + g * 32:L.font + g * 32 + 32]
        for y in range(16):
            w = b[y * 2] << 8 | b[y * 2 + 1]
            for x in range(16):
                if w >> (15 - x) & 1:
                    im.putpixel((g % cols * 17 + x, g // cols * 17 + y), 255)
    return im


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出三国志列伝的人物、城、頭像")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--out")
    ap.add_argument("--scale", type=int, default=1)
    args = ap.parse_args()
    rom = R.load(args.rom)
    args.out = args.out or os.path.join(HERE, "output", *(["cn"] if R.layout(rom).region == "C" else []))
    os.makedirs(os.path.join(args.out, "portraits"), exist_ok=True)

    p_head = ["劇本", "編號", "姓名", "讀音", "城號", "城", "所屬君主", "身分"] + PERSON_HEAD + ["武器碼", "武器", "攻撃力1", "攻撃力2"]
    c_head = ["劇本", "城號", "城", "X", "Y", "勢力", "君主", "太守"] + CITY_HEAD
    p_rows, c_rows = persons(rom), city_rows(rom)
    write_csv(os.path.join(args.out, "persons.csv"), p_head, p_rows)
    write_csv(os.path.join(args.out, "cities.csv"), c_head, c_rows)

    names = R.names(rom)
    for n in range(R.N_FACES):
        face_image(rom, n, args.scale).save(os.path.join(args.out, "portraits", f"P{n:03d}_{names[n]}.png"))
    font_sheet(rom).save(os.path.join(args.out, "font.png"))
    m = map_image(rom)
    m.save(os.path.join(args.out, "map.png"))
    label_map(rom, m).save(os.path.join(args.out, "map_labeled.png"))

    try:
        import openpyxl
    except ImportError:
        print("openpyxl not installed: skipped retsuden.xlsx")
    else:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for title, head, rows in (("persons", p_head, p_rows), ("cities", c_head, c_rows)):
            ws = wb.create_sheet(title)
            ws.append(head)
            for r in rows:
                ws.append(r)
        wb.save(os.path.join(args.out, "retsuden.xlsx"))
    print(f"persons {len(p_rows)}, cities {len(c_rows)}, portraits {R.N_FACES}, map {m.width}x{m.height} → {args.out}")


if __name__ == "__main__":
    main()
