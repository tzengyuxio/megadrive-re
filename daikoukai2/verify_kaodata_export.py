#!/usr/bin/env python3
"""Check a koukai2-md kaodata dataset against the ROM decoding.

1. Every character face and expression and every portrait rendered with the reference renderer (tools/kaodata.py,
   spec §6) must equal rom.Rom.face_rgb of its face code (portraits 128-133 with the grey palette), which
   verify_faces.py checks against the game.
2. checksums.json must equal the checksums recomputed from the dataset (with the expressions).

Usage: .venv/bin/python daikoukai2/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from export_kaodata import VIP_ID, WOMAN_FACE, WOMAN_ID
from rom import DEFAULT_ROM, FACE_PALETTE, GREY_PALETTE, HEROES, SFC_PORTRAITS, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 koukai2-md")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]

    def rgba(face: dict) -> bytes:
        return kaodata.to_rgba(kaodata.compose_display(meta, blobs, face), colors)

    def want(code: int) -> bytes:
        pal = GREY_PALETTE if SFC_PORTRAITS <= code < 0x8000 else FACE_PALETTE
        return b"".join(bytes(c) + b"\xff" for c in rom.face_rgb(code, pal))

    codes = {p["id"]: [p["face"]] + ([SFC_PORTRAITS + p["id"]] if p["id"] < HEROES else []) for p in rom.persons()}
    codes.update({VIP_ID + v["id"]: [v["face"]] for v in rom.vips()})
    codes.update({WOMAN_ID + w["id"]: [WOMAN_FACE + w["id"]] for w in rom.women()})
    bad_ch = [c["id"] for c in meta["characters"]
              if [rgba(f) for f in [c["face"], *c.get("expressions", [])]] != [want(k) for k in codes[c["id"]]]]
    bad_pt = [n for n in range(len(meta["portraits"])) if rgba({"portrait": n}) != want(n)]
    n_ch, n_pt = len(meta["characters"]), len(meta["portraits"])
    n_ex = sum(len(c.get("expressions", [])) for c in meta["characters"])
    print(f"[render] characters {n_ch - len(bad_ch)}/{n_ch} (with {n_ex} expressions), "
          f"portraits {n_pt - len(bad_pt)}/{n_pt} match the ROM"
          + (f" (NG {bad_ch[:10]} {bad_pt[:10]})" if bad_ch or bad_pt else ""))
    missing = sorted(set(codes) - {c["id"] for c in meta["characters"]})
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG") + (f"; missing characters {missing[:10]}" if missing else ""))
    errors = len(bad_ch) + len(bad_pt) + (not sums_ok) + len(missing)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
