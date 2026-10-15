#!/usr/bin/env python3
"""Build data/kanji_ext.json: the MD version's 2-byte kanji codes -> kanji.

The MD and SFC versions list the same 352 persons in the same order with the same readings, but number
their kanji differently. Pairing the name records of the two ROMs gives MD code -> SFC code, and the SFC
code -> kanji table (superfamicom-re san2/data/kanji_ext.json, itself derived from the PC person table and
checked glyph by glyph) gives the kanji. Every pair is checked: the MD glyph must be pixel-identical to the
SFC glyph, and the pairing must be one-to-one.

Usage: .venv/bin/python san2/tools/build_kanji_map.py [--sfc-repo ~/works/superfamicom-re]
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from rom import DEFAULT_ROM, KANJI_EXT, Rom


def load_sfc(repo: str):
    spec = importlib.util.spec_from_file_location("sfc_san2_rom", os.path.join(repo, "san2", "rom.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    ap = argparse.ArgumentParser(description="由 SFC 版的漢字碼對照推出 MD 版的對照")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--sfc-repo", default=os.path.expanduser("~/works/superfamicom-re"))
    args = ap.parse_args()
    sfc_mod = load_sfc(args.sfc_repo)
    sfc = sfc_mod.Rom(os.path.join(args.sfc_repo, "roms", "Super Sangokushi II (Japan).zip"))
    sfc_kanji = sfc_mod.load_kanji()
    md = Rom(args.rom)
    pairs: dict[int, int] = {}
    for a, b in zip(md.persons(), sfc.persons()):
        assert a["reading"] == b["reading"], (a["id"], a["reading"], b["reading"])
        assert len(a["kanji_codes"]) == len(b["kanji_codes"]), a["id"]
        for x, y in zip(a["kanji_codes"], b["kanji_codes"]):
            assert pairs.setdefault(x, y) == y, (hex(x), hex(y))
    assert len(set(pairs.values())) == len(pairs), "not one-to-one"
    bad = [f"{x:04X}" for x, y in pairs.items() if md.glyph(x) != sfc.glyph(y)]
    assert not bad, f"glyphs differ: {bad}"
    out = {"_source": "superfamicom-re san2/data/kanji_ext.json via the SFC name records (same persons, same order)"}
    out.update({f"{x:04X}": sfc_kanji[y] for x, y in sorted(pairs.items())})
    with open(KANJI_EXT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
        f.write("\n")
    print(f"{len(pairs)} codes, glyphs identical to the SFC ones → {KANJI_EXT}")


if __name__ == "__main__":
    main()
