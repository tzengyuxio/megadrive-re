#!/usr/bin/env python3
"""匯出 MD 信長の野望・覇王伝 的人物、劇本人物、城、大名、各種名稱表與頭像。

Usage: .venv/bin/python haouden/export.py [--rom ROM] [--out DIR]

Writes persons.csv (person ids 0-819), person_scenarios.csv (3 scenarios, persons present at the start),
future_persons.csv (persons appearing later), castles.csv (110 castles x 3 scenarios), daimyo.csv,
provinces.csv, titles.csv, treasures.csv, princesses.csv, historic_battles.csv, terrains.csv (+ haouden.xlsx)
and faces/ (927 face ids, 40 x 48).
"""
import argparse
import csv
import os

from PIL import Image
from rom import DEFAULT_ROM, FACE_H, FACE_W, SCENARIO_COUNT, SCENARIO_YEARS, STATS, Rom

HERE = os.path.dirname(os.path.abspath(__file__))


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(path)


def face_label(rom: Rom, fid: int) -> str:
    s = rom.face_source(fid)
    return f"專屬 P{s[1]}" if s[0] == "portrait" else f"組合 組{s[1]} {s[2]:04X}"


def person_rows(rom: Rom) -> list[dict]:
    rows = []
    for pid, m in rom.person_master().items():
        r = m["first"]
        sc, kind, _ = m["appear"][0]
        rows.append({"Id": pid, "姓": r["surname"], "名": r["given"], "其他名": "、".join(m["names"][1:]),
                     "生年": r["born"], **{s: r[s] for s in STATS},
                     "初登場": f"劇本{sc + 1}" + ("開始" if kind == "start" else f" {r['year']}年登場"),
                     "登場": "、".join(f"{s + 1}{'' if k == 'start' else '後'}" for s, k, _ in m["appear"]),
                     "頭像Id": pid, "頭像": face_label(rom, pid)})
    return rows


def scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        s = rom.scenario(sc)
        heads = {d["head"] for d in s["daimyo"]}
        castle_of = {p["addr"]: c for c in s["castles"] for p in c["members"]}
        year = SCENARIO_YEARS[sc]
        for p in s["persons"]:
            c = castle_of.get(p["addr"])
            d = next((x for x in s["daimyo"] if c and x["addr"] == c["daimyo"]), None)
            rank = "大名" if p["addr"] in heads else "城主" if c and c["lord"] == p["addr"] else "家臣" if c else ""
            rows.append({"劇本": sc + 1, "年": year, "Slot": p["slot"], "RAM": f"${p['addr']:06X}", "Id": p["id"],
                         "姓": p["surname"], "名": p["given"], "生年": p["born"], "年齢": year - p["born"],
                         **{st: p[st] for st in STATS}, "気合": p["kiai"], "忠誠": p["loyalty"], "知行": p["fiefs"],
                         "身分": rank, "城": s["castles"][p["castle"]]["name"] if p["castle"] < 110 else p["castle"],
                         "大名家": d["head_person"]["surname"] if d else "",
                         "Unknown24": p["b24"], "Unknown25": p["b25"], "Unknown26": p["b26"],
                         "Unknown27": p["b27"], "Unknown29": p["b29"], "Unknown30": p["b30"],
                         "Unknown32hi": p["b32_hi"], "Unknown38_40": p["b38"], "Unknown42": p["w42"]})
    return rows


def future_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        castles = rom.scenario_castles(sc)
        for f in rom.future_persons(sc):
            rows.append({"劇本": sc + 1, "No": f["no"], "登場年": f["year"], "Id": f["id"], "姓": f["surname"],
                         "名": f["given"], "生年": f["born"], **{st: f[st] for st in STATS},
                         "城": castles[f["castle"]]["name"] if f["castle"] < 110 else f["castle"],
                         "Unknown1": f["b1"], "Unknown2": f["b2"], "Unknown24": f["b24"], "Unknown25": f["b25"],
                         "Unknown28_29": f["tail"]})
    return rows


def castle_rows(rom: Rom) -> list[dict]:
    prov = rom.string_table("provinces")
    siege = rom.siege_types()
    cells = rom.castle_cells()
    rows = []
    for sc in range(SCENARIO_COUNT):
        s = rom.scenario(sc)
        d_by_addr = {d["addr"]: d for d in s["daimyo"]}
        for c in s["castles"]:
            d = d_by_addr.get(c["daimyo"])
            lord = c["members"][0] if c["members"] else None
            rows.append({"劇本": sc + 1, "Id": c["id"], "名": c["name"], "国": prov[c["province"]],
                         "大名家": d["head_person"]["surname"] + d["head_person"]["given"] if d else "",
                         "城主": lord["surname"] + lord["given"] if lord else "", "武將數": len(c["members"]),
                         "本城(推測)": c["main"], "規模": c["size"], "防": c["defense"], "貫": c["kan"],
                         "人": c["people"], "商": c["commerce"], "練": c["training"], "治": c["order"],
                         "兵": c["soldiers"], "銭": c["money"], "糧": c["food"], "鉄砲": c["guns"], "馬": c["horses"],
                         "地圖格x": cells[c["id"]][0], "地圖格y": cells[c["id"]][1],
                         "無城戰場城類": f"0x{siege[c['id']]:02X}", "Unknown0": c["head0"], "Unknown16": c["b16"],
                         "Unknown26": c["b26"], "Unknown41": c["b41"]})
    return rows


def daimyo_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        for d in rom.scenario(sc)["daimyo"]:
            h = d["head_person"]
            rows.append({"劇本": sc + 1, "Slot": d["slot"], "當主": h["surname"] + h["given"], "當主Id": h["id"],
                         "城數": len(d["castles"]), "城": "、".join(c["name"] for c in d["castles"]),
                         "貢献": d["contribution"], "家紋(推測)": d["crest"], "Unknown4": d["b4"],
                         "Unknown5_35": d["relations"], "Unknown37": d["b37"], "Unknown38": d["b38"],
                         "Unknown39": d["b39"]})
    return rows


def list_rows(names: list[str], col: str) -> list[dict]:
    return [{"Id": i, col: n} for i, n in enumerate(names)]


def historic_rows(rom: Rom) -> list[dict]:
    castles = rom.scenario_castles(0)
    return [{"Id": i, "合戦": n, "城": castles[c]["name"]}
            for i, (n, c) in enumerate(zip(rom.string_table("battles"), rom.historic_battle_castles()))]


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"已匯出 {len(rows)} 筆 → {path}")


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    try:
        from openpyxl import Workbook
    except ImportError:
        print("openpyxl 未安裝，略過 .xlsx")
        return
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


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 MD 信長の野望・覇王伝 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {
        "人物": person_rows(rom), "劇本人物": scenario_rows(rom), "後登場人物": future_rows(rom),
        "城": castle_rows(rom), "大名": daimyo_rows(rom),
        "国": list_rows(rom.string_table("provinces"), "国"), "官位": list_rows(rom.string_table("titles"), "官位"),
        "家宝": list_rows(rom.string_table("treasures"), "家宝"), "姫": list_rows(rom.string_table("princesses"), "名"),
        "合戦": historic_rows(rom), "地形": list_rows(rom.string_table("terrains"), "地形"),
    }
    names = ("persons", "person_scenarios", "future_persons", "castles", "daimyo", "provinces", "titles",
             "treasures", "princesses", "historic_battles", "terrains")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    write_xlsx(sheets, os.path.join(args.out, "haouden.xlsx"))

    names_by_id = {r["Id"]: r["姓"] + r["名"] for r in sheets["人物"]}
    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    for fid in rom.face_ids():
        tag = names_by_id.get(fid, "")
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(fid), os.path.join(faces, f"{fid:03d}{'_' + tag if tag else ''}.png"))
    print(f"頭像 {len(rom.face_ids())} 張 → {faces}")


if __name__ == "__main__":
    main()
