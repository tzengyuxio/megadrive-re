#!/usr/bin/env python3
"""匯出 MD ヨーロッパ戦線 的劇本、將領、領袖、經歷、都市、兵器、地形與頭像。

Usage: .venv/bin/python europe/export.py [--rom ROM] [--out DIR]

Writes scenarios.csv, persons.csv (person ids 0-99), scenario_generals.csv, leaders.csv, biographies.csv,
cities.csv, weapons.csv, map_cells.csv (6 x 1600 cells: terrain, cell word) (+ europe.xlsx when openpyxl is
installed), portraits/ (000-119) and maps/ (terrain sketches of the 6 battle maps, plain and with city names;
the game's map pictures are not decoded yet).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    DEFAULT_ROM,
    FACE_COUNT,
    FACE_H,
    FACE_W,
    MAP_SIZE,
    PERSON_COUNT,
    SCENARIO_COUNT,
    TERRAIN_NAMES,
    WEAPON_KINDS,
    Rom,
    nations,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
CELL = 16
TERRAIN_RGB = [(0, 40, 120), (255, 60, 60), (200, 200, 200), (120, 200, 90), (240, 220, 140), (60, 120, 255),
               (90, 150, 140), (170, 140, 90), (30, 110, 40), (140, 110, 70), (230, 230, 80)]


def png(w: int, h: int, rgb: list, path: str) -> Image.Image:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(path)
    return im


def side(slot: int) -> str:
    return "枢軸" if slot < 20 else "連合"


def available(v: int) -> str:
    return "開戦時" if v == 0 else f"{1940 + (v >> 4)}/{v & 15}"


def scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in rom.scenarios():
        gens = rom.generals(s["id"])
        rows.append({"劇本": s["id"], "名稱": s["title"], "日期": f"{s['year']}/{s['month']}/{s['day']}",
                     "地圖": s["map"], "枢軸將領": sum(g["slot"] < 20 for g in gens),
                     "連合將領": sum(g["slot"] >= 20 for g in gens), "都市數": len(rom.cities(s["id"])),
                     "ROM位址": f"0x{rom.block_offset(s['id']):05X}", "header(+0..15)": s["header"].hex(" ")})
    return rows


def general_values(g: dict) -> dict:
    return {"國籍": nations(g["nation"]), "國籍bits": f"{g['nation']:02X}", "指揮": g["指揮"], "魅力": g["魅力"],
            "歩兵": g["歩兵"], "砲兵": g["砲兵"], "戦車": g["戦車"], "経験": g["経験"],
            "Unknown12": g["unknown12"], "Unknown13": g["unknown13"], "Unknown14": g["unknown14"],
            "Unknown19": g["unknown19"], "Unknown21": g["unknown21"]}


def person_rows(rom: Rom) -> list[dict]:
    return [{"id": p["id"], "姓名": p["name"], "陣營": p["side"][0], **general_values(p),
             "登場劇本": " ".join(map(str, p["scenarios"])), "領袖": "是" if p["id"] >= PERSON_COUNT else "",
             "經歷": "".join(rom.biography(p["id"])).strip() if p["id"] < PERSON_COUNT else ""}
            for p in rom.persons()]


def scenario_general_rows(rom: Rom) -> list[dict]:
    return [{"劇本": sc, "槽": g["slot"], "陣營": side(g["slot"]), "id": g["id"], "姓名": g["name"],
             **general_values(g)} for sc in range(1, SCENARIO_COUNT + 1) for g in rom.generals(sc)]


def leader_rows(rom: Rom) -> list[dict]:
    return [{"記錄": g["slot"], "id": g["id"], "姓名": g["name"], "國籍": nations(g["nation"]),
             "國籍bits": f"{g['nation']:02X}", "Unknown19": g["unknown19"],
             "Unknown21(推測04元首05參謀長)": g["unknown21"]} for g in rom.leaders()]


def biography_rows(rom: Rom) -> list[dict]:
    names = {p["id"]: p["name"] for p in rom.persons()}
    return [{"id": pid, "姓名": names[pid], **{f"第{k + 1}行": line for k, line in enumerate(rom.biography(pid))}}
            for pid in range(PERSON_COUNT)]


def city_rows(rom: Rom) -> list[dict]:
    weapons = rom.weapons()
    rows = []
    for sc in range(1, SCENARIO_COUNT + 1):
        terrain = rom.map_terrain(sc)
        for c in rom.cities(sc):
            rows.append({"劇本": sc, "記錄": c["id"], "名稱": c["name"], "x": c["x"], "y": c["y"],
                         "地形": TERRAIN_NAMES[terrain[c["y"] * MAP_SIZE + c["x"]]],
                         "弾薬": c["弾薬"], "燃料": c["燃料"], "食料": c["食料"],
                         "第二組三值(未解)": " ".join(map(str, c["values2"])), "耐久": c["耐久"],
                         "耐久上限": c["耐久max"],
                         "駐軍": "、".join(f"{weapons[g['weapon']]['name']}×{g['count']}" for g in c["garrison"]),
                         "陣營": c["side"], "旗標(+64)": f"{c['flags']:02X}"})
    return rows


def weapon_rows(rom: Rom) -> list[dict]:
    return [{"id": w["id"], "名稱": w["name"], "國籍": nations(w["nation"]), "國籍bits": f"{w['nation']:02X}",
             "種別": WEAPON_KINDS[w["kind"]] if w["kind"] < len(WEAPON_KINDS) else w["kind"],
             "登場(推測)": available(w["available"]), "AP": w["AP"], "AT": w["AT"], "防": w["防"], "速": w["速"],
             "射": w["射"], "Unknown10": w["unknown10"], "Unknown11": w["unknown11"], "Unknown13": w["unknown13"]}
            for w in rom.weapons()]


def cell_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(1, SCENARIO_COUNT + 1):
        m = rom.map_number(sc)
        raw, words = rom.terrain_raw(sc), rom.map_words(m)
        for i in range(MAP_SIZE * MAP_SIZE):
            rows.append({"地圖": m, "x": i % MAP_SIZE, "y": i // MAP_SIZE, "地形": TERRAIN_NAMES[raw[i] & 15],
                         "地形碼": raw[i] & 15, "旗標(高4位,未解)": raw[i] >> 4, "格碼(未解)": f"{words[i]:04X}"})
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"已匯出 {len(rows)} 筆 → {path}")


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        ws.append(list(rows[0]))
        for r in rows:
            ws.append(list(r.values()))
        ws.freeze_panes = "B2"
    wb.save(path)
    print(f"已匯出 → {path}")


def font(size: int):
    try:
        return ImageFont.truetype(LABEL_FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def map_images(rom: Rom, out: str) -> None:
    """Terrain sketches: one colour per terrain code, CELL pixels per map cell."""
    os.makedirs(out, exist_ok=True)
    f = font(14)
    for s in rom.scenarios():
        terrain = rom.map_terrain(s["id"])
        im = Image.new("RGB", (MAP_SIZE * CELL, MAP_SIZE * CELL))
        dr = ImageDraw.Draw(im)
        for i, t in enumerate(terrain):
            x, y = i % MAP_SIZE * CELL, i // MAP_SIZE * CELL
            dr.rectangle((x, y, x + CELL - 1, y + CELL - 1), fill=TERRAIN_RGB[t])
        base = os.path.join(out, f"map{s['map']}_{s['title']}")
        im.save(base + ".png")
        for c in rom.cities(s["id"]):
            dr.text((c["x"] * CELL + CELL // 2, c["y"] * CELL - 2), c["name"], fill="white", anchor="mb", font=f,
                    stroke_width=3, stroke_fill="black")
        im.save(base + "_cities.png")


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 MD ヨーロッパ戦線資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"劇本": scenario_rows(rom), "人物": person_rows(rom), "劇本將領": scenario_general_rows(rom),
              "領袖": leader_rows(rom), "經歷": biography_rows(rom), "都市": city_rows(rom),
              "兵器": weapon_rows(rom), "地圖格": cell_rows(rom)}
    files = ("scenarios", "persons", "scenario_generals", "leaders", "biographies", "cities", "weapons", "map_cells")
    for rows, fn in zip(sheets.values(), files):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "europe.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    names = {p["id"]: p["name"] for p in rom.persons()}
    for n in range(FACE_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n),
            os.path.join(portraits, f"{n:03d}" + (f"_{names[n]}" if n in names else "") + ".png"))
    map_images(rom, os.path.join(args.out, "maps"))
    print(f"頭像 {FACE_COUNT} 張、戰場地形示意 {SCENARIO_COUNT} 張 → {args.out}")


if __name__ == "__main__":
    main()
