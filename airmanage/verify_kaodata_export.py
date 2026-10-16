#!/usr/bin/env python3
"""Check an air-md kaodata dataset against the ROM decoding.

1. Every portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal rom.Rom.face_rgb
   in the game's palette (verify_faces.py checks it against VRAM, CRAM and the screen), in Rom.faces() order;
   the groups must follow the face kind and the maker portraits carry the maker names of the ROM.
2. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python airmanage/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from export_kaodata import GROUPS, full_width
from rom import DEFAULT_ROM, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 air-md")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    faces = rom.faces()
    makers = {m["face_image"]: full_width(m["name"]) for m in rom.makers()}

    def ok(n: int, pt: dict) -> bool:
        f = faces[n]
        want = b"".join(bytes(c) + b"\xff" for row in rom.face_rgb(f["kind"], f["image"]) for c in row)
        got = kaodata.to_rgba(kaodata.compose_display(meta, blobs, {"portrait": n}), colors)
        name = makers[f["image"]] if f["kind"] == 2 else None
        return got == want and pt.get("group") == GROUPS[f["kind"]] and pt.get("name") == name

    pts = meta["portraits"]
    bad = [n for n, pt in enumerate(pts) if n >= len(faces) or not ok(n, pt)]
    print(f"[render] portraits {len(pts) - len(bad)}/{len(faces)} match the ROM (picture, group, maker name)"
          + (f" (NG {bad[:10]})" if bad else ""))
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad) + (not sums_ok) + (len(pts) != len(faces)) + bool(meta["characters"])
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
