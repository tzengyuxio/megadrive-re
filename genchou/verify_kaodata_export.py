#!/usr/bin/env python3
"""Check a genchou-md kaodata dataset against the ROM decoding.

1. Every character and portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal
   rom.face_tiles (checked against the game's VRAM, CRAM and screen by verify_faces.py) in the face palette.
2. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python genchou/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
import rom as R
from export_kaodata import CHILD_ID, WOMEN_ID, characters


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 genchou-md")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.load(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    pal = R.face_palette(rom)

    def rgba(face: dict) -> bytes:
        return kaodata.to_rgba(kaodata.compose_display(meta, blobs, face), colors)

    def want(code: int, woman: bool = False) -> bytes:
        return b"".join(bytes(pal[v]) + b"\xff" for v in R.tiles_pixels(R.face_tiles(rom, code, woman)))

    faces = {c["id"]: (c["code"], c["woman"]) for c in characters(rom)}
    bad_ch = [c["id"] for c in meta["characters"] if rgba(c["face"]) != want(*faces[c["id"]])]
    bad_pt = [n for n in range(len(meta["portraits"])) if rgba({"portrait": n}) != (
        want(n) if n < R.WOMAN_PORTRAIT else want(n - R.WOMAN_PORTRAIT, True))]
    n_ch, n_pt = len(meta["characters"]), len(meta["portraits"])
    women = sum(WOMEN_ID <= c["id"] < CHILD_ID for c in meta["characters"])
    kids = sum(c["id"] >= CHILD_ID for c in meta["characters"])
    print(f"[render] characters {n_ch - len(bad_ch)}/{n_ch} ({women} women, {kids} children), portraits {n_pt - len(bad_pt)}/{n_pt} "
          f"match the ROM" + (f" (NG {bad_ch[:10]} {bad_pt[:10]})" if bad_ch or bad_pt else ""))
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad_ch) + len(bad_pt) + (not sums_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
