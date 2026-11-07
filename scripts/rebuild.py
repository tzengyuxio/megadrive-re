"""Rebuild the output/ folder of one or more games from the ROMs (in the game library, tools/paths.py), so output/
can be thrown away at any time.

Usage: .venv/bin/python scripts/rebuild.py GAME [GAME ...] | --all [--dry-run]

The steps of a game are found by file name, in this order:
  1. <game>/export.py         CSV, XLSX, PNG (once more per ROM in EXPORT_ROMS, which export.py puts in a subfolder)
  2. <game>/*_manifest.py     portrait-sheet/1 manifests, then each sheet.json under output/portrait-sheet/ is
                              rendered with the portrait-sheet skill
Not run: verify_*.py (they check, they don't build; MAME / GPGX), export_kaodata.py (its --out is usually the
kaodata repo), tools/parts_sheet.py (reads an exported kaodata dataset), san2/tools/build_kanji_map.py (reads
superfamicom-re, writes the tracked san2/data/). A failing step stops that game. winning has no export.py.
"""
import argparse
import glob
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "bin", "python")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from paths import ORIGINAL_MD

RENDER = os.path.expanduser("~/.claude/skills/portrait-sheet/render.py")
# other editions, exported to output/usa/ or output/cn/
EXPORT_ROMS = {"genchou": ["Genghis Khan II - Clan of the Gray Wolf (USA).zip"],
               "zenkoku": ["Nobunaga's Ambition (USA).zip"],
               "retsuden": ["San Guo Zhi Lie Zhuan - Luan Shi Qun Ying (China).zip"]}


def games() -> list[str]:
    return sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(ROOT, "*", "export.py")))


def steps(game: str) -> list[list[str]]:
    export = os.path.join(ROOT, game, "export.py")
    runs = [[PY, export]] + [[PY, export, "--rom", os.path.join(ORIGINAL_MD, r)] for r in EXPORT_ROMS.get(game, [])]
    return runs + [[PY, p] for p in sorted(glob.glob(os.path.join(ROOT, game, "*_manifest.py")))]


def renders(game: str) -> list[list[str]]:
    sheets = sorted(glob.glob(os.path.join(ROOT, game, "output", "portrait-sheet", "*", "sheet.json")))
    return [[PY, "-I", RENDER, s, os.path.join(os.path.dirname(s), "out")] for s in sheets]


def run(cmd: list[str], dry: bool) -> float:
    print("  " + " ".join(os.path.relpath(c, ROOT) if c.startswith(ROOT) else c for c in cmd), flush=True)
    if dry:
        return 0.0
    t = time.monotonic()
    subprocess.run(cmd, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    return time.monotonic() - t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="only list the steps")
    args = ap.parse_args()
    todo = games() if args.all else args.games
    unknown = set(todo) - set(games())
    if not todo or unknown:
        sys.exit(f"games: {' '.join(games())}" + (f"\nunknown: {' '.join(sorted(unknown))}" if unknown else ""))
    failed = []
    for game in todo:
        print(game, flush=True)
        total = 0.0
        try:
            for cmd in steps(game):
                total += run(cmd, args.dry_run)
            if any(c[1].endswith("_manifest.py") for c in steps(game)):
                if not os.path.exists(RENDER):
                    print(f"  {RENDER} not found, sheets not rendered", flush=True)
                for cmd in renders(game) if os.path.exists(RENDER) else []:
                    total += run(cmd, args.dry_run)
        except subprocess.CalledProcessError as e:
            failed.append(game)
            print(f"  FAILED ({e.returncode})", flush=True)
            continue
        if not args.dry_run:
            print(f"  {total:.0f} s", flush=True)
    if failed:
        sys.exit(f"failed: {' '.join(failed)}")


if __name__ == "__main__":
    main()
