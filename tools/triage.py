#!/usr/bin/env python3
"""First look at MD ROMs: header, checksum, vectors, KOEI LZ table block, Shift-JIS game words.

Usage: .venv/bin/python tools/triage.py [ROM ...]     # default: every ROM in roms/
Prints a Markdown table.
"""
import argparse
import glob
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from koei_lz import find_tables

WORDS = ["武将", "兵士", "君主", "大名", "シナリオ", "金", "兵糧"]


def load_rom(path: str) -> bytes:
    """ROM bytes from a .zip (first .md/.bin/.gen inside) or a plain file."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            return z.read(next(n for n in z.namelist() if n.lower().endswith((".md", ".bin", ".gen"))))
    with open(path, "rb") as f:
        return f.read()


def header(rom: bytes) -> dict:
    """Fields of the header at 0x100 and whether the stored checksum matches the word sum from 0x200."""
    h = rom[0x100:0x200]
    s = sum(int.from_bytes(rom[i:i + 2], "big") for i in range(0x200, len(rom) - 1, 2)) & 0xFFFF
    stored = int.from_bytes(h[0x8E:0x90], "big")
    return {"system": h[0:16].decode("ascii", "replace").strip(), "copyright": h[16:32].decode("ascii", "replace").strip(),
            "title_jp": h[32:80].decode("cp932", "replace").strip(), "title_en": h[80:128].decode("cp932", "replace").strip(),
            "serial": h[128:142].decode("ascii", "replace").strip(), "checksum_ok": stored == s,
            "rom_end": int.from_bytes(h[0xA4:0xA8], "big"), "sram": h[0xB0:0xBC].hex() if h[0xB0:0xB2] == b"RA" else "",
            "region": h[0xF0:0xF3].decode("ascii", "replace").strip(),
            "reset": int.from_bytes(rom[4:8], "big"), "vblank": int.from_bytes(rom[0x78:0x7C], "big")}


def triage(path: str) -> dict:
    rom = load_rom(path)
    sjis = sum(rom.count(w.encode("cp932")) for w in WORDS)
    t = find_tables(rom)
    return {"file": os.path.basename(path).removesuffix(".zip"), "size": f"{len(rom) >> 10} KB", **header(rom),
            "lz": f"{t:#x}" if t >= 0 else "", "sjis": sjis}


def main() -> None:
    ap = argparse.ArgumentParser(description="MD ROM 初步分診")
    ap.add_argument("roms", nargs="*")
    args = ap.parse_args()
    paths = args.roms or sorted(glob.glob(os.path.join(REPO, "roms", "*.zip")))
    print("| ROM | size | copyright | serial | title | sum | SRAM | reset | VBlank | KOEI LZ | SJIS |")
    print("|-----|------|-----------|--------|-------|-----|------|-------|--------|---------|------|")
    for p in paths:
        r = triage(p)
        print(f"| {r['file']} | {r['size']} | {r['copyright']} | {r['serial']} | {r['title_jp']} / {r['title_en']} "
              f"| {'ok' if r['checksum_ok'] else 'NG'} | {r['sram']} | {r['reset']:#x} | {r['vblank']:#x} "
              f"| {r['lz'] or '—'} | {r['sjis']} |", flush=True)


if __name__ == "__main__":
    main()
