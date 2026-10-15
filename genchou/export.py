#!/usr/bin/env python3
"""Export MD Genghis Khan II data: persons, family blocks, women, countries, houses, places of the 4 scenarios (CSV,
UTF-8-BOM), the portraits and every person's face (PNG), the composed-face heads, and an .xlsx with every table
(needs openpyxl).

Usage: .venv/bin/python genchou/export.py [--rom ROM] [--out DIR]
"""
import argparse
import csv
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rom as R

GRADES = "EDCBA"
STATUS = {0: "", 1: "家臣(推測)", 2: "領主(推測)", 3: "國王"}
P_HEAD = ["劇本", "年", "格", "姓名", "王家", "所在國", "身分", "體力", "體力上限", "戦闘", "政治", "魅力", "指揮", "年齢",
          "文化(推測)", "+19 其他 bits", "頭像碼"]


def face_image(rom: bytes, code: int, woman: bool = False, scale: int = 1) -> Image.Image:
    pal = R.face_palette(rom)
    im = Image.new("RGB", (R.FACE_W * 8, R.FACE_H * 8))
    im.putdata([pal[v] for v in R.tiles_pixels(R.face_tiles(rom, code, woman))])
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST) if scale > 1 else im


def person_row(rom: bytes, n: int, p: dict, houses: dict, places: list[str]) -> list:
    return [n + 1, R.year(rom, n), p["slot"], p["name"], houses.get(p["house"], ""),
            places[p["country"]] if p["country"] < len(places) else p["country"], STATUS.get(p["status"], p["status"]),
            p["hp"], p["hp_max"], GRADES[p["war"]], GRADES[p["pol"]], GRADES[p["cha"]], GRADES[p["lead"]], p["age"],
            p["culture"], f"{p['flags']:02X}", f"{p['face']:04X}"]


def tables(rom: bytes) -> dict[str, tuple[list[str], list[list]]]:
    persons, family, children, countries, houses, women, places = [], [], [], [], [], [], []
    for n in range(R.SCENARIO_COUNT):
        world = n > 0
        names = R.place_names(rom, world)
        hs = {h["id"]: h["name"] for h in R.houses(rom, n)}
        persons += [person_row(rom, n, p, hs, names) for p in R.persons(rom, n)]
        for f in R.families(rom, n):
            family += [[hs.get(f["house"], f["house"])] + person_row(rom, n, p, hs, names) for p in f["persons"]]
            children += [[n + 1, R.year(rom, n), hs.get(f["house"], f["house"]), c["name"], c["raw"]]
                         for c in f["children"]]
        for c in R.countries(rom, n):
            countries.append([n + 1, R.year(rom, n), c["id"], names[c["id"]], hs.get(c["house"], c["house"]),
                              " ".join(names[a] for a in c["adjacent"]), c["gold"], c["food"], c["population"],
                              *c["mix"], c["b20"], c["v21"], c["v22"], c["v23"], " ".join(map(str, c["troops"])),
                              c["rest"]])
        ps = {p["slot"]: p["name"] for p in R.persons(rom, n)}
        wn = {w["id"]: w["name"] for w in R.women(rom)}
        for h in R.houses(rom, n):
            houses.append([n + 1, R.year(rom, n), h["id"], h["name"], ps.get(h["king"], ""),
                           names[h["first_country"]] if h["first_country"] is not None else "",
                           wn.get(h["woman"], ""), h["culture"]])
    for w in R.women(rom):
        women.append([w["id"], w["name"], w["country"], w["b13"], w["b14"], f"{w['face']:04X}"])
    for world in (False, True):
        places += [["世界" if world else "蒙古", k, name, x, y]
                   for k, (name, (x, y)) in enumerate(zip(R.place_names(rom, world), R.place_pos(rom, world)))
                   if name]
    return {
        "persons": (P_HEAD, persons),
        "family": (["家族所屬王家"] + P_HEAD, family),
        "children": (["劇本", "年", "王家", "姓名", "其餘 7 bytes（未解）"], children),
        "countries": (["劇本", "年", "國號", "國", "王家", "相鄰", "金", "食糧", "人口", "農業%(推測)", "牧畜%(推測)",
                       "特産%(推測)", "街%(推測)", "+20", "+21", "+22", "+23", "部隊 16 兵科(推測)", "+40.. 未解"],
                      countries),
        "houses": (["劇本", "年", "王家號", "王家", "國王", "第一個國", "后妃", "+34 文化(推測)"], houses),
        "women": (["號", "姓名", "所在國", "+13", "+14", "頭像碼"], women),
        "places": (["地圖", "號", "地名", "標籤 x", "標籤 y"], places),
    }


def write_csv(path: str, head: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(head)
        w.writerows(rows)


def heads_sheet(rom: bytes) -> Image.Image:
    """56 heads: each with all parts version 0 and all parts version 1, 2x."""
    im = Image.new("RGB", (14 * 44 * 2, 8 * 52 * 2), (40, 40, 40))
    for head in range(56):
        g, m = divmod(head, 7)
        for v in range(2):
            code = 0x8000 | g << 12 | m << 9 | sum(v << b for b in R.PART_BITS)
            im.paste(face_image(rom, code, scale=2), ((m * 2 + v) * 88, g * 104))
    return im


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 Genghis Khan II 的人物、國、王家、頭像")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = R.load(args.rom)
    for d in ("portraits", "faces"):
        os.makedirs(os.path.join(args.out, d), exist_ok=True)

    tabs = tables(rom)
    for name, (head, rows) in tabs.items():
        write_csv(os.path.join(args.out, f"{name}.csv"), head, rows)

    for n in range(R.PORTRAIT_COUNT):
        face_image(rom, n).save(os.path.join(args.out, "portraits", f"P{n:03d}.png"))
    done = set()
    for n in range(R.SCENARIO_COUNT):
        rows = R.persons(rom, n) + [p for f in R.families(rom, n) for p in f["persons"]]
        for p in rows:
            if (p["name"], p["face"]) in done:
                continue
            done.add((p["name"], p["face"]))
            safe = p["name"].replace("/", "_").replace(" ", "_")
            face_image(rom, p["face"]).save(os.path.join(args.out, "faces", f"{p['face']:04X}_{safe}.png"))
    for w in R.women(rom):
        face_image(rom, w["face"], True).save(os.path.join(args.out, "faces", f"w{w['id']:02d}_{w['name']}.png"))
    heads_sheet(rom).save(os.path.join(args.out, "heads.png"))

    try:
        import openpyxl
    except ImportError:
        print("openpyxl not installed: skipped genchou.xlsx")
    else:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for name, (head, rows) in tabs.items():
            ws = wb.create_sheet(name)
            ws.append(head)
            for r in rows:
                ws.append(r)
        wb.save(os.path.join(args.out, "genchou.xlsx"))
    print(", ".join(f"{k} {len(v[1])}" for k, v in tabs.items())
          + f", portraits {R.PORTRAIT_COUNT}, faces {len(done) + len(R.women(rom))} → {args.out}")


if __name__ == "__main__":
    main()
