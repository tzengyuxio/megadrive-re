#!/usr/bin/env python3
"""Check a genchou-md kaodata dataset against the ROM decoding.

1. Every character and portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal
   rom.face_tiles (checked against the game's VRAM, CRAM and screen by verify_faces.py) in the face palette.
2. Japanese version: every character's nameZh must be the one in data/name_zh.json (none where it is null);
   USA version: no nameZh.
3. checksums.json must equal the checksums recomputed from the dataset.

With the Mega-CD version (portraits with addedIn): the CD portraits must equal cd.slot (checked against the game
by verify_cd_faces.py) and the CD's characters must equal cd.face_tiles; every cartridge character whose CD face
differs (a new portrait, or a pre-rendered composite that differs by one tile from the cartridge's parts, cd.py) must
have it as its one expression, labelled Mega-CD 版, and no other character may have one.

Usage: .venv/bin/python genchou/verify_kaodata_export.py --dataset <dir> [--rom ROM] [--cd IMAGE]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import cd
import kaodata
import rom as R
from export_kaodata import CD_PORTRAITS, CHILD_ID, WOMEN_ID, cd_characters, characters, names_zh


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 genchou-md")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--cd", default=cd.DEFAULT_IMAGE)
    args = ap.parse_args()
    rom = R.load(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    with_cd = any(p.get("addedIn") == "CD" for p in meta["portraits"])
    img = cd.load(args.cd) if with_cd else None
    colors = meta["palettes"][0]["colors"]
    pal = R.face_palette(rom)

    def rgba(face: dict) -> bytes:
        return kaodata.to_rgba(kaodata.compose_display(meta, blobs, face), colors)

    def want(code: int, woman: bool = False) -> bytes:
        return b"".join(bytes(pal[v]) + b"\xff" for v in R.tiles_pixels(R.face_tiles(rom, code, woman)))

    def want_cd(code: int, woman: bool = False) -> bytes:
        return b"".join(bytes(pal[v]) + b"\xff" for v in R.tiles_pixels(cd.face_tiles(img, code, woman)))

    found = characters(rom)
    new, changed = cd_characters(found, img) if img else ([], {})
    faces = {c["id"]: (c["code"], c["woman"]) for c in found}
    cd_faces = {c["id"]: (c["code"], c["woman"]) for c in new}
    # the CD's face of each character that has one different from the cartridge's: the Mega-CD 版 expression
    cd_expr = {i: (code, faces[i][1]) for i, code in changed.items()}
    cd_expr |= {i: f for i, f in faces.items() if img and i not in changed and f[0] & 0x8000 and want_cd(*f) != want(*f)}
    bad_ch = [c["id"] for c in meta["characters"] if rgba(c["face"]) != (
        want_cd(*cd_faces[c["id"]]) if c["id"] in cd_faces else want(*faces[c["id"]]))]
    bad_ch += [c["id"] for c in meta["characters"] if c.get("expressions") and (
        c["id"] not in cd_expr or len(c["expressions"]) != 1 or c["expressions"][0].get("label") != "Mega-CD 版"
        or rgba(c["expressions"][0]) != want_cd(*cd_expr[c["id"]]))]
    bad_ch += [i for i in cd_expr if "expressions" not in next(c for c in meta["characters"] if c["id"] == i)]
    shown = sorted(i for i, (code, w) in cd_faces.items() if code & 0x8000 and want_cd(code, w) != want(code, w))
    bad_pt = [n for n in range(R.PORTRAIT_COUNT) if rgba({"portrait": n}) != (
        want(n) if n < R.WOMAN_PORTRAIT else want(n - R.WOMAN_PORTRAIT, True))]
    added = [p for p in meta["portraits"][R.PORTRAIT_COUNT:] if p.get("addedIn") == "CD"]
    for k, p in enumerate(added):
        n, code = R.PORTRAIT_COUNT + k, int(p["code"], 16)
        tiles = cd.slot(img, CD_PORTRAITS[k]) if k < len(CD_PORTRAITS) else cd.face_tiles(img, code)
        if rgba({"portrait": n}) != b"".join(bytes(pal[v]) + b"\xff" for v in R.tiles_pixels(tiles)):
            bad_pt.append(n)
    bad_pt += list(range(R.PORTRAIT_COUNT + len(added), len(meta["portraits"])))
    n_ch, n_pt = len(meta["characters"]), len(meta["portraits"])
    women = sum(WOMEN_ID <= c["id"] < CHILD_ID for c in meta["characters"])
    kids = sum(c["id"] >= CHILD_ID for c in meta["characters"])
    print(f"[render] characters {n_ch - len(bad_ch)}/{n_ch} ({women} women, {kids} children), portraits {n_pt - len(bad_pt)}/{n_pt} "
          f"match the ROM" + (f" (NG {bad_ch[:10]} {bad_pt[:10]})" if bad_ch or bad_pt else ""))
    if img:
        print(f"[Mega-CD] {len(new)} characters ({len(shown)} with a pre-rendered composite the cartridge's parts don't "
              f"draw), {len(cd_expr)} expressions, {len(added)} portraits")
    zh = names_zh() if R.layout(rom).region == "J" else {}
    bad_zh = [c["id"] for c in meta["characters"] if c.get("nameZh") != zh.get(c["id"])]
    print(f"[nameZh] {n_ch - len(bad_zh)}/{n_ch} = data/name_zh.json" + (f" (NG {bad_zh[:10]})" if bad_zh else ""))
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad_ch) + len(bad_pt) + len(bad_zh) + (not sums_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
