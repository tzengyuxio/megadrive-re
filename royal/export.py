#!/usr/bin/env python3
"""匯出 MD ロイヤルブラッド 的劇本、人物、家、領地、部隊、戰場、頭像與地圖。

Usage: .venv/bin/python royal/export.py [--rom ROM] [--out DIR] [--scale N]

Writes scenarios.csv, characters.csv (4 scenarios, present characters), houses.csv, provinces.csv (4 scenarios),
units.csv, battle_maps.csv (+ royal.xlsx when openpyxl is installed), faces/ (64 characters), advisers/ (4),
unit_faces/ (23), map.png (strategy map), screen_1.png / screen_2.png (the two main screen layouts), panel.png and
battle_maps/ (30 terrain sketches; the game's battle screen is not decoded yet).
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    ADVISER_FIRST,
    BATTLE_H,
    BATTLE_W,
    DEFAULT_ROM,
    FACE_COUNT,
    PROVINCE_COUNT,
    SCENARIO_COUNT,
    STATUS,
    TERRAIN,
    UNIT_CLASS,
    UNIT_COUNT,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
TERRAIN_RGB = {0: (120, 200, 90), 1: (255, 0, 255), 2: (60, 60, 255), 3: (255, 60, 60), 4: (30, 120, 40),
               5: (190, 160, 90), 6: (130, 100, 70), 12: (240, 220, 80), 13: (110, 110, 110), 14: (80, 80, 80),
               15: (80, 80, 80)}


def png(w: int, h: int, rgb: list, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def house(rom: Rom, h: int) -> str:
    return "" if h == 0xFF else rom.house_name(h)


def province(rom: Rom, k: int) -> str:
    return "" if k == 0xFF else f"{k + 1}:{rom.province_name(k)}"


def scenario_rows(rom: Rom) -> list[dict]:
    return [{"劇本": s + 1, "標題": rom.scenario_title(s), "年數差": rom.scenario_years(s),
             "人物數": len(rom.persons(s)), "家數": len(rom.houses(s)),
             "支配領地數": sum(p["owner"] != 0xFF for p in rom.provinces(s))} for s in range(SCENARIO_COUNT)]


def character_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        for c in rom.persons(s):
            rows.append({"劇本": s + 1, "編號": c["id"], "姓名": c["name"], "年齢": c["age"], "知力": c["int"],
                         "武力": c["war"], "魅力": c["charm"], "所在領地": province(rom, c["province"]),
                         "家": house(rom, c["house"]), "身分": STATUS.get(c["status"], str(c["status"])),
                         "一族(推定)": house(rom, c["clan"]), "+11(未知)": c["unk11"],
                         "姓名表+16(未知)": f"{rom.name_record(c['id'])['unk16']:02X}", "頭像": f"C{c['id']:02d}"})
    return rows


def house_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        provs = rom.provinces(s)
        for h in rom.houses(s):
            owned = [p["id"] + 1 for p in provs if p["owner"] == h["house"]]
            rows.append({"劇本": s + 1, "槽": h["slot"], "編號": h["house"], "家": h["name"],
                         "当主": rom.person_name(h["head"]), "領地數": len(owned), "領地": " ".join(map(str, owned)),
                         "旗標(未知)": f"{h['flags']:02X}"})
    return rows


def province_rows(rom: Rom) -> list[dict]:
    units = rom.units()
    rows = []
    for s in range(SCENARIO_COUNT):
        persons = rom.persons(s)
        for p in rom.provinces(s):
            members = [c["name"] for c in persons if c["province"] == p["id"]]
            rows.append({"劇本": s + 1, "編號": p["id"] + 1, "領地": p["name"], "支配家": house(rom, p["owner"]),
                         "金": p["gold"], "食料": p["food"], "兵": p["soldiers"], "開発": p["develop"],
                         "作物": p["crops"], "民忠": p["loyalty"], "旗標(未知)": p["flags"],
                         "部隊候補(種類:兵力/末位元組)": " ".join(f"{units[t]['name']}:{n}/{b}" for t, n, b in p["units"]),
                         "人物數": len(members), "人物": " ".join(members),
                         "相鄰": " ".join(str(n + 1) for n in rom.province_neighbours(p["id"])),
                         "地圖標記格": "{},{}".format(*rom.province_mark(p["id"]))})
    return rows


def unit_rows(rom: Rom) -> list[dict]:
    return [{"編號": u["id"], "名稱": u["name"], "+11(攻擊?)": u["attack"], "+12(防禦?)": u["defence"],
             "+15(初期兵力)": u["strength"], "+16(未知)": u["unk16"], "+17(未知)": u["unk17"],
             "+18(類別)": f"{u['class']:02X} {UNIT_CLASS.get(u['class'], '?')}", "頭像": f"U{u['id']:02d}"}
            for u in rom.units()]


def battle_rows(rom: Rom) -> list[dict]:
    rows = []
    for k in range(PROVINCE_COUNT):
        g = rom.battle_terrain(k)
        rows.append({"編號": k + 1, "領地": rom.province_name(k), "寬": BATTLE_W, "高": BATTLE_H,
                     "地形(高4位元，每列以/分隔)": "/".join("".join(f"{v:x}" for v in g[r * BATTLE_W:(r + 1) * BATTLE_W])
                                               for r in range(BATTLE_H)),
                     "地形種類": " ".join(sorted({TERRAIN.get(v, f"{v:X}") for v in g}))})
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        fields = list(dict.fromkeys(k for r in rows for k in r))
        ws.append(fields)
        for r in rows:
            ws.append([r.get(k, "") for k in fields])
        ws.freeze_panes = "A2"
    wb.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 MD ロイヤルブラッド 劇本／人物／家／領地／部隊／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"劇本": scenario_rows(rom), "人物": character_rows(rom), "家": house_rows(rom),
              "領地": province_rows(rom), "部隊": unit_rows(rom), "戰場": battle_rows(rom)}
    for rows, name in zip(sheets.values(), ["scenarios", "characters", "houses", "provinces", "units", "battle_maps"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "royal.xlsx"))
    except ImportError:
        print("openpyxl 未安裝，略過 .xlsx")

    units = rom.units()
    faces = [("faces", n, False, f"C{n:02d}_{rom.person_name(n)}") for n in range(ADVISER_FIRST)]
    faces += [("advisers", n, False, f"A{n - ADVISER_FIRST}") for n in range(ADVISER_FIRST, FACE_COUNT)]
    faces += [("unit_faces", n, True, f"U{n:02d}_{units[n]['name']}") for n in range(UNIT_COUNT)]
    for sub, n, unit, name in faces:
        os.makedirs(os.path.join(args.out, sub), exist_ok=True)
        png(40, 48, rom.face_rgb(n, unit), os.path.join(args.out, sub, f"{name}.png"), args.scale)
    png(*rom.map_rgb(), os.path.join(args.out, "map.png"), args.scale)
    for n in range(2):
        png(*rom.screen_rgb(n), os.path.join(args.out, f"screen_{n + 1}.png"), args.scale)
    png(*rom.panel_rgb(), os.path.join(args.out, "panel.png"), args.scale)
    d = os.path.join(args.out, "battle_maps")
    os.makedirs(d, exist_ok=True)
    for k in range(PROVINCE_COUNT):
        g = rom.battle_terrain(k)
        rgb = [TERRAIN_RGB.get(g[y // 16 * BATTLE_W + x // 16], (0, 0, 0)) for y in range(BATTLE_H * 16)
               for x in range(BATTLE_W * 16)]
        png(BATTLE_W * 16, BATTLE_H * 16, rgb, os.path.join(d, f"{k + 1:02d}_{rom.province_name(k)}.png"), args.scale)

    print(f"已匯出 {len(sheets['人物'])} 筆人物（64 人 × 4 劇本中登場者）、{len(sheets['家'])} 筆家、"
          f"{len(sheets['領地'])} 筆領地、{len(sheets['部隊'])} 種部隊 → {args.out}")
    print(f"頭像 人物 {ADVISER_FIRST}＋相談役 {FACE_COUNT - ADVISER_FIRST}＋部隊 {UNIT_COUNT}；戰略地圖 120×144；"
          f"戰場示意 {PROVINCE_COUNT} 張")


if __name__ == "__main__":
    main()
