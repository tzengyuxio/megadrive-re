#!/usr/bin/env python3
"""匯出 MD 太閤立志伝 的人物、名表、勢力、城、字串表與頭像。

Usage: .venv/bin/python taikou/export.py [--rom ROM] [--out DIR]

Writes names.csv (716), persons.csv (713 records), factions.csv (20), castles.csv (125), strings.csv
(+ taikou.xlsx when openpyxl is installed), faces/ (one PNG per person record), portraits/ (000-257) and
composite_parts.png (the 12 face types: every variant of the 5 parts, in build order).
The big map and the battle fields are not rendered yet (see docs/ROM_FORMAT.md).
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    COMP_ORDER,
    COMP_TYPES,
    COMP_VARIANTS,
    DEFAULT_ROM,
    FACE_BYTES,
    FACE_H,
    FACE_W,
    PORTRAIT_COUNT,
    SKILL_GRADES,
    STATS,
    STRING_TABLES,
    Rom,
    md_rgb,
    tiles_pixels,
)

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK = 8   # cells per map block side


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(path)


def full_name(p: dict) -> str:
    return p["surname"] + p["given"]


def faction_names(rom: Rom, persons: list[dict]) -> dict[int, str]:
    """faction id -> its daimyo's name ("" when the faction has none)."""
    return {f["id"]: full_name(persons[f["daimyo"]]) if f["daimyo"] != 0xFF else "" for f in rom.factions()}


def name_rows(rom: Rom) -> list[dict]:
    return [{"Id": n["id"], "姓": n["surname"], "名": n["given"], "頭像碼": f"{n['face']:04X}",
             "頭像": f"組合 型{n['face'] >> 8 & 15}" if n["face"] & 0x8000 else f"專屬 {n['face']:03d}"}
            for n in rom.names()]


def person_rows(rom: Rom, persons: list[dict]) -> list[dict]:
    castles, ranks = rom.castles(), rom.string_table("ranks")
    skills = rom.string_table("skills")
    fname = faction_names(rom, persons)
    rows = []
    for p in persons:
        f, c = p["faction"], p["castle"]
        row = {"記錄": p["record"], "Id": p["id"], "姓名": full_name(p), "開始時": "登場" if p["start"] else "後登場",
               "所属(大名)": "浪人" if f == 0xFF else fname.get(f, "") or f"勢力{f}（無大名）",
               "勢力Id": "" if f == 0xFF else f, "身分": ranks[p["rank"]] if p["rank"] < len(ranks) else p["rank"],
               "居城(推測)": castles[c]["name"] if c < len(castles) else "", "居城Id(推測)": c,
               "政略Lv": p["政略Lv"], "戦術Lv": p["戦術Lv"], **{s: p[s] for s in STATS},
               **{sk: SKILL_GRADES[v] for sk, v in zip(skills, p["skills"])}, "頭像碼": f"{p['face']:04X}"}
        for i, (loc, x, y) in enumerate(p["positions"]):
            row[f"位置{i + 1}(未解)"] = f"{loc}/{x},{y}"
        row.update({"Unknown14_25": p["raw"][14:26].hex(" "), "Unknown30(推測兵數)": p["w30"], "Unknown32": p["b32"],
                    "Unknown33": p["b33"], "Unknown35": p["b35"], "Unknown36": p["b36"],
                    "Unknown47_59": p["tail"].hex(" ")})
        rows.append(row)
    return rows


def faction_rows(rom: Rom, persons: list[dict]) -> list[dict]:
    castles = rom.castles()
    fname = faction_names(rom, persons)
    rows = []
    for f in rom.factions():
        rows.append({"Id": f["id"], "大名": fname[f["id"]], "大名記錄": "" if f["daimyo"] == 0xFF else f["daimyo"],
                     "本城(推測)": castles[f["castle"]]["name"] if f["castle"] < len(castles) else "",
                     "本城Id(推測)": f["castle"],
                     "城數": sum(1 for c in castles if c["state"] is not None and c["faction"] == f["id"]),
                     "Unknown1_20(對各勢力)": " ".join(f"{b:02X}" for b in f["relations"]),
                     "Unknown22": f["w22"], "Unknown24": f["b24"], "Unknown26": f["w26"],
                     "Unknown28_33": f["tail"].hex(" ")})
    return rows


def castle_rows(rom: Rom, persons: list[dict]) -> list[dict]:
    castles = rom.castles()
    fname = faction_names(rom, persons)
    rows = []
    for c in castles:
        (bx, by), (cx, cy) = c["block"], c["cell"]
        row = {"Id": c["id"], "名": c["name"], "相鄰": "、".join(castles[n]["name"] for n in c["neighbours"]),
               "地圖x(格)": bx * BLOCK + cx, "地圖y(格)": by * BLOCK + cy, "區塊位置": c["location"],
               "格x": cx, "格y": cy, "Unknown18": c["b18"]}
        s = c["state"]
        if s is None:
            row.update({"勢力": "（開始時無）"})
        else:
            f, lord = c["faction"], c["lord"]
            row.update({"勢力": "" if f == 0xFF else fname.get(f, "") or f"勢力{f}",
                        "城主(推測)": full_name(persons[lord]) if lord < len(persons) else "",
                        "城主記錄(推測)": lord, "城圖示(+15 低 2 位)": c["s15"] & 3,
                        "狀態+0(城Id)": s[0], "狀態+3": c["s3"], "狀態+4": c["s4"], "狀態+6": c["s6"], "狀態+8": c["s8"],
                        "狀態+10": c["s10"], "狀態+11": c["s11"], "狀態+12": c["s12"], "狀態+14": c["s14"],
                        "狀態+15": f"{c['s15']:02X}", "狀態+16": c["s16"]})
        rows.append(row)
    keys = list(max(rows, key=len))
    return [{k: r.get(k, "") for k in keys} for r in rows]


def string_rows(rom: Rom) -> list[dict]:
    return [{"表": name, "ROM_Offset": f"0x{STRING_TABLES[name][0]:05X}", "Id": i, "字串": s}
            for name in STRING_TABLES for i, s in enumerate(rom.string_table(name))]


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


def parts_sheet(rom: Rom, path: str) -> None:
    """One row per type: for each part in build order, its 4 variants (tiles outside the part's run grey)."""
    w, h = FACE_W * 8, FACE_H * 8
    pal = [md_rgb(c) for c in rom.face_palette()]
    gap = 4
    sheet = Image.new("RGB", (len(COMP_ORDER) * (COMP_VARIANTS * (w + 1) + gap), COMP_TYPES * (h + 1)), (40, 40, 40))
    for t in range(COMP_TYPES):
        for k, (p, _) in enumerate(COMP_ORDER):
            for v in range(COMP_VARIANTS):
                first, tiles = rom.composite_part(t, p, v)
                cells = range(first, first + len(tiles) // 32)
                buf = bytearray(FACE_BYTES)
                buf[32 * first:32 * first + len(tiles)] = tiles
                px = tiles_pixels(bytes(buf))
                rgb = [pal[c] if (i // w // 8) * FACE_W + i % w // 8 in cells else (128, 128, 128)
                       for i, c in enumerate(px)]
                im = Image.new("RGB", (w, h))
                im.putdata(rgb)
                sheet.paste(im, (k * (COMP_VARIANTS * (w + 1) + gap) + v * (w + 1), t * (h + 1)))
    sheet.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 MD 太閤立志伝 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    persons = rom.persons()

    sheets = {"名表": name_rows(rom), "人物": person_rows(rom, persons), "勢力": faction_rows(rom, persons),
              "城": castle_rows(rom, persons), "字串表": string_rows(rom)}
    for rows, fn in zip(sheets.values(), ("names", "persons", "factions", "castles", "strings")):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "taikou.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    for p in persons:
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(p["face"]),
            os.path.join(faces, f"{p['record']:03d}_{full_name(p)}.png"))
    for n in range(PORTRAIT_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(portraits, f"{n:03d}.png"))
    parts_sheet(rom, os.path.join(args.out, "composite_parts.png"))
    print(f"頭像 {len(persons)} 人＋{PORTRAIT_COUNT} 張、組合臉部件總覽 → {args.out}")


if __name__ == "__main__":
    main()
