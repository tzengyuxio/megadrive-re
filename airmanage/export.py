#!/usr/bin/env python3
"""匯出 MD エアーマネジメント 大空に賭ける 的都市、劇本、距離、機種、製造商、頭像與大地圖。

Usage: .venv/bin/python airmanage/export.py [--rom ROM] [--out DIR] [--scale N]

Writes cities.csv, scenario_cities.csv, distances.csv, matrix2.csv (unsolved), aircraft.csv, makers.csv
(+ airmanage.xlsx when openpyxl is installed), faces/ (33 portraits) + faces.png, world_map.png and
world_map_cities.png (with the 22 city markers where the HQ-selection screen draws them).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import CITY_COUNT, CITY_TYPE_NAMES, DEFAULT_ROM, MAP_ROW, SCENARIOS, Rom, md_rgb

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing


def font(size: int):
    try:
        return ImageFont.truetype(LABEL_FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
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
    wb.save(path)
    print(f"已匯出 → {path}")


def city_rows(rom: Rom) -> list[dict]:
    cities = rom.cities()
    out = []
    for c in cities:
        row = {"番號": c["index"], "都市": c["name"], "都市(半形)": c["kana"], "機場": c["airport"],
               "預設航空公司": c["airline"], "類型": CITY_TYPE_NAMES[c["type"]], "類型值": c["type"],
               "地圖X": c["x"], "地圖Y": c["y"],
               "[未解]第二組航空公司名": c["airline2"], "[未解]座標X": c["world_x"], "[未解]座標Y": c["world_y"]}
        for k, (dest, b2, b3) in enumerate(c["routes"]):
            row[f"[推測]初期航線{k + 1}"] = cities[dest]["name"]
            row[f"[未解]航線{k + 1}值1"] = b2
            row[f"[未解]航線{k + 1}值2"] = b3
        out.append(row)
    return out


def scenario_rows(rom: Rom) -> list[dict]:
    names = [c["name"] for c in rom.cities()]
    hq = rom.hq_table()
    out = []
    for s, (sname, year) in enumerate(SCENARIOS):
        for v in rom.scenario_cities(s):
            c = v["index"]
            out.append({"劇本": s + 1, "劇本名": sname, "開始年": year, "番號": c, "都市": names[c],
                        "人口(万人)": v["population"], "経済力": v["economy"], "経済力ランク": rom.rank(v["economy"]),
                        "観光地": v["tourism"], "観光地ランク": rom.rank(v["tourism"]), "スロット数": v["slots"],
                        "本社スロット": v["hq_slots"], "[推測]本社初期資金(万$)": v["funds"],
                        **{f"[未解]本社參數{k + 1}": hq[c][k] for k in range(4)}})
    return out


def matrix_rows(rom: Rom, m: list[list]) -> list[dict]:
    names = [c["name"] for c in rom.cities()]
    return [{"都市": names[a], **{names[b]: ("" if m[a][b] is None else m[a][b]) for b in range(CITY_COUNT)}}
            for a in range(CITY_COUNT)]


def aircraft_rows(rom: Rom) -> list[dict]:
    return [{"番號": a["index"], "機種": a["name"], "英數名": a["ascii"], "メーカー": a["maker"], "座席数": a["seats"],
             "航続距離(km)": a["range"], "価格(万$)": a["price"], "燃料費": a["fuel"], "発売年": a["release"],
             "生産終了年": "" if a["end"] == 2100 else a["end"], "[未解]+16": a["unk14"],
             "[未驗證]側面圖": a["side_picture"], "[未驗證]上視圖": "" if a["top_picture"] is None else a["top_picture"]}
            for a in rom.aircraft()]


def maker_rows(rom: Rom) -> list[dict]:
    air = rom.aircraft()
    return [{"番號": m["index"], "メーカー": m["name"], "代表色(MD)": f"{m['color']:04X}",
             "頭像": f"MAKER {m['face_image']}", "調色盤": m["face_palette"],
             "機種": " ".join(air[k]["name"] for k in m["aircraft"])} for m in rom.makers()]


def save_rgb(px: list[list[tuple]], path: str, scale: int) -> Image.Image:
    h, w = len(px), len(px[0])
    im = Image.new("RGB", (w, h))
    im.putdata([c for row in px for c in row])
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)
    return im


def export_faces(rom: Rom, out: str, scale: int) -> None:
    os.makedirs(os.path.join(out, "faces"), exist_ok=True)
    tiles = []
    for f in rom.faces():
        name = f"{f['file']}_{f['image']:02d}"
        tiles.append((name, save_rgb(rom.face_rgb(f["kind"], f["image"]), os.path.join(out, "faces", f"{name}.png"),
                                     scale)))
    cols = 8
    w, h = tiles[0][1].size
    sheet = Image.new("RGB", (cols * (w + 4), (len(tiles) + cols - 1) // cols * (h + 18)), (32, 32, 32))
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(tiles):
        x, y = i % cols * (w + 4), i // cols * (h + 18)
        sheet.paste(im, (x, y))
        d.text((x, y + h + 2), name, fill=(255, 255, 255), font=font(11))
    sheet.save(os.path.join(out, "faces.png"))


def export_map(rom: Rom, out: str, scale: int) -> None:
    pal, _, _ = rom.world_map()
    rgb = [md_rgb(c) for c in pal]
    px = [[rgb[c] for c in row] for row in rom.world_map_pixels()]
    save_rgb(px, os.path.join(out, "world_map.png"), scale)
    im = save_rgb(px, os.path.join(out, "world_map_cities.png"), 3)
    d = ImageDraw.Draw(im)
    for c in rom.cities():
        # the 8 x 8 marker sprite: screen (x, y + 24), the map's top row at screen y 8 * MAP_ROW
        x, y = 3 * c["x"], 3 * (c["y"] + 24 - 8 * MAP_ROW)
        d.rectangle([x, y, x + 23, y + 23], outline=(255, 0, 0), width=2)
        d.text((x + 26, y), c["name"], fill=(255, 255, 255), font=font(14), stroke_width=2, stroke_fill=(0, 0, 0))
    im.save(os.path.join(out, "world_map_cities.png"))


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 MD エアーマネジメント 大空に賭ける 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    sheets = {"cities": city_rows(rom), "scenario_cities": scenario_rows(rom),
              "distances": matrix_rows(rom, rom.distances()), "matrix2": matrix_rows(rom, rom.matrix2()),
              "aircraft": aircraft_rows(rom), "makers": maker_rows(rom)}
    for name, rows in sheets.items():
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "airmanage.xlsx"))
    except ImportError:
        print("openpyxl 未安裝，略過 airmanage.xlsx")
    export_faces(rom, args.out, args.scale)
    export_map(rom, args.out, args.scale)
    print(f"頭像 {len(rom.faces())} 張、大地圖 → {args.out}")


if __name__ == "__main__":
    main()
