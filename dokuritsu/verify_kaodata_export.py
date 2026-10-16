#!/usr/bin/env python3
"""Check a liberty-md kaodata dataset against the ROM decoding.

1. Every character and portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal
   rom.Rom.face_rgb of its face code, which verify_faces.py checks against the game's VRAM and screen; characters
   must be the person ids 0-249 with the ROM names and codes, portraits 0-173 must carry their code and the groups
   and names of export_kaodata.portrait_groups.
2. Every composite code of the 4 types x 4^5 part variants, composed from the dataset, must equal rom.face_rgb.
3. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python dokuritsu/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from export_kaodata import code_parts, portrait_groups
from rom import DEFAULT_ROM, PORTRAIT_COUNT, TYPE_COUNT, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 liberty-md")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    persons = {p["id"]: p for p in rom.persons()}
    groups = portrait_groups(rom)

    def rgba(face: dict) -> bytes:
        return kaodata.to_rgba(kaodata.compose_display(meta, blobs, face), colors)

    def want(code: int) -> bytes:
        return b"".join(bytes(c) + b"\xff" for c in rom.face_rgb(code))

    def face_ok(c: dict) -> bool:
        p, f = persons[c["id"]], c["face"]
        code_ok = f.get("code") == f"{p['face']:04X}" if p["face"] & 0x8000 else f.get("portrait") == p["face"]
        return code_ok and rgba(f) == want(p["face"])

    bad_ch = [c["id"] for c in meta["characters"] if c["name"] != persons[c["id"]]["name"] or not face_ok(c)]
    bad_pt = [n for n, pt in enumerate(meta["portraits"]) if rgba({"portrait": n}) != want(n)
              or pt.get("code") != f"{n:04X}" or {k: v for k, v in pt.items() if k in ("group", "name")} != groups.get(n, {})]
    n_ch, n_pt = len(meta["characters"]), len(meta["portraits"])
    missing = sorted(set(persons) - {c["id"] for c in meta["characters"]})
    print(f"[render] characters {n_ch - len(bad_ch)}/{n_ch} (face, code and name), portraits {n_pt - len(bad_pt)}/{n_pt} "
          f"(pixels, code, group and name) match the ROM" + (f" (NG {bad_ch[:10]} {bad_pt[:10]})" if bad_ch or bad_pt else "")
          + (f"; persons missing {missing}" if missing else ""))
    codes = [0x8000 | t << 10 | v for t in range(TYPE_COUNT) for v in range(1024)]
    bad_cc = []
    for code in codes:
        t, parts = code_parts(code)
        if rgba({"variant": t, "parts": parts}) != want(code):
            bad_cc.append(f"{code:04X}")
    print(f"[composite] {len(codes) - len(bad_cc)}/{len(codes)} codes composed from the parts match the ROM"
          + (f" (NG {bad_cc[:10]})" if bad_cc else ""))
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad_ch) + len(bad_pt) + len(missing) + len(bad_cc) + (not sums_ok) + (n_pt != PORTRAIT_COUNT)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
