#!/usr/bin/env python3
"""Check a san3-md kaodata dataset against the ROM decoding.

1. Every character (plain and composite faces) and every portrait rendered with the reference renderer
   (tools/kaodata.py, spec §6) must equal rom.Rom.face_rgb, which verify_faces.py checks against the game's VRAM.
2. checksums.json must equal the checksums recomputed from the dataset.
3. With the Mega-CD version (portraits with addedIn): the CD portraits, the CD characters and every Mega-CD 版
   expression must equal the CD's faces (cd.Disc, checked against the game by verify_cd_faces.py); every person
   whose CD face differs from the cartridge's has one (labelled Mega-CD 版, its face 卡帶版); the unused CD portraits (D563) equal the cartridge's
   composite of their code.

Usage: .venv/bin/python san3/verify_kaodata_export.py [--dataset DIR] [--rom ROM] [--cd IMAGE]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import cd
import kaodata
from rom import DEFAULT_ROM, FACE_COUNT, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 san3-md")
    ap.add_argument("--dataset", default=os.path.join(HERE, "output", "kaodata", "san3-md"))
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--cd", default=cd.DEFAULT_IMAGE)
    args = ap.parse_args()
    rom = Rom(args.rom)
    persons = rom.persons()
    meta, blobs = kaodata.load_dataset(args.dataset)
    disc = cd.Disc(args.cd) if any(p.get("addedIn") for p in meta["portraits"]) else None
    colors = meta["palettes"][0]["colors"]

    def rgba(face: dict) -> bytes:
        return kaodata.to_rgba(kaodata.compose_display(meta, blobs, face), colors)

    def want(face: int, src: Rom = rom) -> bytes:
        return b"".join(bytes(c) + b"\xff" for c in src.face_rgb(face))

    chars = meta["characters"]
    cd_persons = disc.persons() if disc else []
    replaced = [q for q in cd_persons if q["name"] != persons[q["id"]]["name"]]    # new ids after the cartridge's
    bad_ch = [c["id"] for c in chars if rgba(c["face"]) != (
        want(persons[c["id"]]["face"]) if c["id"] < len(persons) else want(replaced[c["id"] - len(persons)]["face"],
                                                                           disc))]
    bad_pt = [n for n in range(FACE_COUNT) if rgba({"portrait": n}) != want(n + 1)]
    added = [p for p in meta["portraits"][FACE_COUNT:] if p.get("addedIn") == "CD"]
    bad_pt += [FACE_COUNT + k for k, p in enumerate(added) if rgba({"portrait": FACE_COUNT + k}) != want(
        int(p["code"], 16), rom if p.get("group") == "未使用" else disc)]      # unused: the cartridge's parts
    bad_pt += list(range(FACE_COUNT + len(added), len(meta["portraits"])))
    n_expr = 0
    for q in cd_persons:
        c, p = chars[q["id"]], persons[q["id"]]
        changed = q["name"] == p["name"] and want(q["face"], disc) != want(p["face"])
        expr = c.get("expressions", [])
        n_expr += bool(expr)
        if changed != bool(expr) or expr and (len(expr) != 1 or rgba(expr[0]) != want(q["face"], disc)
                                              or expr[0].get("label") != "Mega-CD 版"
                                              or c["face"].get("label") != "卡帶版"):
            bad_ch.append(c["id"])
    n_ch, n_pt = len(chars), len(meta["portraits"])
    n_comp = sum("variant" in c["face"] for c in chars)
    print(f"[render] characters {n_ch - len(bad_ch)}/{n_ch} ({n_comp} composite), portraits {n_pt - len(bad_pt)}/{n_pt}"
          " match the ROM" + (f" (NG {bad_ch[:10]} {bad_pt[:10]})" if bad_ch or bad_pt else ""))
    if disc:
        print(f"[Mega-CD] {len(chars) - len(persons)} characters, {len(added)} portraits, {n_expr} expressions")
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad_ch) + len(bad_pt) + (not sums_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
