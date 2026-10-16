"""匯出 MD 大航海時代II 的人物、VIP、女性、船種、港、道具、發見物、字串表、頭像與世界地圖。

Usage: .venv/bin/python daikoukai2/export.py [--rom ROM] [--out DIR]

Writes persons.csv, vips.csv, women.csv, ship_types.csv, ports.csv, items.csv, discoveries.csv, strings.csv (UTF-8
with BOM), faces/ (persons, VIPs and women), portraits/ (000-133; 128-133 in the hero select's grey palette),
packs/ (per composite pack, every part n = 0-7 of every slot), world_map.png (one pixel per cell: sea, land and
other tiles by cell value; the map's own tile graphics are not decoded) and world_map_ports.png (2x, labelled).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    COMPOSITE_PACKS,
    DEFAULT_ROM,
    FACE_PALETTE,
    GREY_PALETTE,
    HEROES,
    MAP_H,
    MAP_W,
    PORTRAIT_COUNT,
    SFC_PORTRAITS,
    STATS,
    STRING_TABLES,
    TRADE_PORTS,
    Rom,
    ram,
)

HERE = os.path.dirname(os.path.abspath(__file__))
WOMAN_FACE = 97


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(path)


def person_rows(rom: Rom) -> list[dict]:
    countries, ports = rom.strings("countries"), rom.ports()
    rows = []
    for p in rom.persons():
        code = p["face"]
        rows.append({
            "Id": p["id"], "RAM": f"{ram(0xD2B96) + 32 * p['id']:06X}", "姓名": p["name"],
            "類別": "主角" if p["id"] < HEROES else "仲間" if p["id"] < 69 else "劇情人物" if p["id"] < 79 else "提督",
            **dict(zip(STATS, p["stats"])), "年齡": p["age"], "航海Lv": p["sail_level"], "航海經驗": p["sail_exp"],
            "戰鬥Lv": p["battle_level"], "戰鬥經驗": p["battle_exp"],
            "國籍": countries[p["country"]] if p["country"] < len(countries) else p["country"],
            "頭像碼": f"{code:04X}", "頭像": f"組合 包{rom.pack_of(code)}" if code & 0x8000 else f"專屬 {code:03d}",
            "母港(推測)": "" if p["port"] == 0xFF else ports[p["port"]]["name"] if p["port"] < len(ports) else p["port"],
            "+17(未解)": p["unk17"], "+25(未解)": p["unk25"], "+26(未解)": p["unk26"], "+28(未解)": p["unk28"],
            "+29(未解)": f"{p['unk29']:04X}", "+31高位(未解)": p["flags31"]})
    return rows


def vip_rows(rom: Rom) -> list[dict]:
    ports = rom.ports()
    return [{"Id": v["id"], "名前": v["name"], "頭像": v["face"], "+4(未解)": v["kind"], "+8(未解)": v["unk8"],
             "+9 港(推測)": ports[v["port"]]["name"] if v["kind"] != 0xFF else "", "+9": v["port"]}
            for v in rom.vips()]


def women_rows(rom: Rom) -> list[dict]:
    ports = rom.ports()
    return [{"Id": w["id"], "名前": w["name"], "頭像($41510)": WOMAN_FACE + w["id"], "+4 年齡(推測)": w["age"],
             "+5 港(推測)": ports[w["port"]]["name"], "+5": w["port"], "+9(未解)": f"{w['unk9']:02X}"}
            for w in rom.women()]


def ship_rows(rom: Rom) -> list[dict]:
    return [{"Id": t["id"], "船種": t["name"], "+4 編號": t["number"], "+5(未解)": f"{t['flags']:02X}",
             "+6(未解)": t["b6"], "+8(未解)": t["w8"], "+10(未解)": t["w10"],
             **{f"規格{i}": t["spec"][i] for i in range(6)}, "規格6 BE16": int.from_bytes(t["spec"][6:8], "big"),
             "規格8": t["spec"][8], "規格9": t["spec"][9], "規格10 BE16(推測 價格)": int.from_bytes(t["spec"][10:12], "big")}
            for t in rom.ship_types()]


def port_rows(rom: Rom) -> list[dict]:
    countries, items = rom.strings("countries"), rom.items()
    rows = []
    for p in rom.ports():
        r = {"Id": p["id"], "港名": p["name"], "x": p["x"], "y": p["y"], "種類": "交易港" if p["id"] < TRADE_PORTS else "補給港",
             "國籍": countries[p["country"]] if p["country"] < 6 else "", "旗標高位(未解)": p["flags"]}
        if "state" in p:
            r.update({"經濟(推測)": p["economy"], "工業(推測)": p["industry"],
                      **{f"占有率_{countries[i]}(推測)": v for i, v in enumerate(p["shares"])},
                      "商品分類價格(未解)": " ".join(map(str, p["price_levels"])), "地域(推測)": p["region"],
                      "道具(推測)": "、".join(items[i]["name"] for i in p["items"] if i < len(items)),
                      "+0(未解)": p["unk0"], "+26(未解)": p["w26"], "+28(未解)": p["b28"], "+29(未解)": p["b29"],
                      "+35(未解)": p["b35"], "+36(未解)": p["b36"]})
        rows.append(r)
    return rows


def item_rows(rom: Rom) -> list[dict]:
    cats = rom.strings("item_categories")
    return [{"Id": i["id"], "名稱": i["name"], "分類": cats[i["category"]] if i["category"] < len(cats) else i["category"],
             "價格(推測)": i["price"], "效果值(推測)": i["power"], "+4(未解)": i["icon"], "說明": i["text"]}
            for i in rom.items()]


def string_rows(rom: Rom) -> list[dict]:
    return [{"表": key, "ROM": f"0x{STRING_TABLES[key][0]:05X}", "序": k, "字串": s}
            for key in STRING_TABLES for k, s in enumerate(rom.strings(key))]


def write_csv(rows: list[dict], path: str) -> None:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def font(size: int):
    for path in ("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def map_images(rom: Rom, out: str) -> None:
    sea, land, other = (40, 70, 140), (90, 140, 60), (230, 200, 90)
    cells = rom.map_cells()
    im = Image.new("RGB", (MAP_W, MAP_H))
    im.putdata([sea if v == 0 else land if v == 0x80 else other for v in cells])
    im.save(os.path.join(out, "world_map.png"))
    big = im.resize((MAP_W * 2, MAP_H * 2), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    f = font(14)
    for p in rom.ports():
        x, y = p["x"] * 2, p["y"] * 2
        dr.rectangle([x - 3, y - 3, x + 3, y + 3], outline="red" if p["id"] < TRADE_PORTS else "yellow", width=2)
        dr.text((x + 6, y), f"{p['id']} {p['name']}", fill="white", anchor="lm", font=f, stroke_width=2,
                stroke_fill="black")
    big.save(os.path.join(out, "world_map_ports.png"))


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 MD 大航海時代II 的資料、頭像與世界地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    tables = {"persons": person_rows(rom), "vips": vip_rows(rom), "women": women_rows(rom),
              "ship_types": ship_rows(rom), "ports": port_rows(rom), "items": item_rows(rom),
              "discoveries": rom.discoveries(), "strings": string_rows(rom)}
    for fn, rows in tables.items():
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
        print(f"{fn}.csv: {len(rows)} rows")

    for sub in ("faces", "portraits", "packs"):
        os.makedirs(os.path.join(args.out, sub), exist_ok=True)
    faces = [(f"{p['id']:03d}_{p['name']}", p["face"]) for p in rom.persons()]
    faces += [(f"vip{v['id']:02d}_{v['name']}", v["face"]) for v in rom.vips()]
    faces += [(f"woman{w['id']:02d}_{w['name']}", WOMAN_FACE + w["id"]) for w in rom.women()]
    for name, code in faces:
        png(40, 48, rom.face_rgb(code), os.path.join(args.out, "faces", f"{name}.png"))
    for n in range(PORTRAIT_COUNT):
        png(40, 48, rom.face_rgb(n, GREY_PALETTE if n >= SFC_PORTRAITS else FACE_PALETTE),
            os.path.join(args.out, "portraits", f"{n:03d}.png"))
    # pack sheets: row n = the face whose every part is n (code 0x8000 | t << 12 | n in all four fields)
    for t in range(COMPOSITE_PACKS):
        sheet = Image.new("RGB", (40, 48 * 8))
        for n in range(8):
            face = Image.new("RGB", (40, 48))
            face.putdata(rom.face_rgb(0x8000 | t << 12 | n << 9 | n << 6 | n << 3 | n))
            sheet.paste(face, (0, 48 * n))
        sheet.resize((120, 48 * 8 * 3), Image.NEAREST).save(os.path.join(args.out, "packs", f"pack{t}.png"))
    print(f"faces/: {len(faces)}, portraits/: {PORTRAIT_COUNT}, packs/: {COMPOSITE_PACKS}")
    map_images(rom, args.out)
    print(f"world_map.png: {MAP_W} x {MAP_H}")


if __name__ == "__main__":
    main()
