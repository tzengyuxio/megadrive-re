#!/usr/bin/env python3
"""Check an air2-md kaodata dataset against the ROM decoding.

1. Every portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal Rom.face_rgb with
   the portrait's palette (the decoding verify_faces.py checks against VRAM, CRAM and the screen), in
   export_kaodata.portrait_faces order (Rom.faces() without the blank-palette descriptors).
2. Every portrait has its kind as group; only the maker portraits have a name (the maker's, NFKC upper case).
3. No portrait has "label" or "code"; there are no characters.
4. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python airmanage2/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from export_kaodata import GROUPS, maker_name, portrait_faces
from rom import DEFAULT_ROM, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 air2-md")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    faces = portrait_faces(rom)
    pts = meta["portraits"]
    bad = []
    for n, f in enumerate(faces[:len(pts)]):
        got = kaodata.to_rgba(kaodata.compose_display(meta, blobs, {"portrait": n}), colors)
        want = b"".join(bytes(c) + b"\xff" for row in rom.face_rgb(f["kind"], f["image"], f["palette"]) for c in row)
        if got != want:
            bad.append(n)
    ok_count = len(pts) == len(faces)
    print(f"[render] portraits {len(pts) - len(bad)}/{len(pts)} match the ROM" + (f" (NG {bad[:10]})" if bad else "")
          + ("" if ok_count else f"; ROM has {len(faces)}"))
    bad_group = [n for n, (p, f) in enumerate(zip(pts, faces))
                 if p.get("group") != GROUPS[f["file"]] or ("name" in p) != (f["file"] == "MAKER")
                 or (f["file"] == "MAKER" and p["name"] != maker_name(f))]
    print(f"[groups] portraits {len(pts) - len(bad_group)}/{len(pts)}: group = kind, maker name only on maker portraits"
          + (f" (NG {bad_group[:10]})" if bad_group else ""))
    bad_keys = [n for n, p in enumerate(pts) if "label" in p or "code" in p]
    print(f"[keys] portraits without label / code: {len(pts) - len(bad_keys)}/{len(pts)}; "
          f"characters {len(meta['characters'])}")
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as fh:
        sums_ok = json.load(fh) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad) + len(bad_group) + len(bad_keys) + (not sums_ok) + (not ok_count) + len(meta["characters"])
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
