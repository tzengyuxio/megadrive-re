"""Copy one game's results into the game library (re-common §11), so the repo's roms/ and output/ can be removed later.

Usage: .venv/bin/python scripts/archive.py GAME [GAME ...] | --all [--library DIR]
       (default ~/game-library; run scripts/rebuild.py first)

What goes where, by file name (GAMES below gives each game's library id, ROMs, fragment folders and extras):
  output/<file>                      -> <id>/<file>                 CSV, XLSX, PNG as they are
  output/<folder>/ of single images  -> <id>/<folder>.cbz           stored (not deflated) zip, one per folder
  output/<folder>/ of anything else  -> <id>/<folder>/              the same rules, one level down
  output/portrait-sheet/*/out/*.png  -> <id>/sheets/                the rendered pages; manifests and copies dropped
  output/kaodata*/, output/<id>-md/  -> not kept                    kaodata datasets: the kaodata repo holds them
  roms/<ROM>.zip                     -> _original/md/<ROM>.zip      and its sha1 (and the sha1 of each file inside)
  roms/megacd/<image>.7z             -> _original/megacd/<image>.7z    in that folder's SHA1SUMS.txt; a Mega-CD game
  roms/megacd/bios/*                 -> _original/megacd/bios/*        also copies the BIOS
Fragment folders (no identity, an overview image already exists) are not kept. Files already in the library are
overwritten, nothing there is deleted. The library README.md of the game and the status table (koei.md, md.md)
are written by hand; the script only says when they are missing.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROMS = os.path.join(ROOT, "roms")
MEGACD = os.path.join(ROMS, "megacd")
# game folder -> library id (koei/... for KOEI games, md/... for the others), ROMs (megacd/... = Mega-CD image),
# fragment folders of output/, extra files of output/ kept although under a skipped folder
GAMES = {
    "airmanage": {"id": "koei/air-md", "roms": ["Air Management - Oozora ni Kakeru (Japan).zip"]},
    "airmanage2": {"id": "koei/air2-md", "roms": ["Air Management II - Koukuuou o Mezase (Japan).zip"]},
    "bushou": {"id": "koei/nobu4-md", "fragments": ["mob_parts"],
               "roms": ["Nobunaga no Yabou - Bushou Fuuunroku (Japan).zip"]},
    "daikoukai": {"id": "koei/koukai-md", "fragments": ["mob_parts"], "roms": ["Daikoukai Jidai (Japan).zip"]},
    "daikoukai2": {"id": "koei/koukai2-md", "roms": ["Daikoukai Jidai II (Japan).zip"]},
    "dokuritsu": {"id": "koei/liberty-md", "roms": ["Liberty or Death (USA).zip"]},
    "europe": {"id": "koei/europe-md", "roms": ["Europa Sensen (Japan).zip"]},
    "genchou": {"id": "koei/genchou-md", "roms": ["Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).zip",
                                                 "Genghis Khan II - Clan of the Gray Wolf (USA).zip",
                                                 "megacd/Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).7z"]},
    "haouden": {"id": "koei/nobu5-md", "roms": ["Nobunaga no Yabou - Haouden (Japan).zip",
                                               "megacd/Nobunaga no Yabou - Haouden (Japan).7z"]},
    "retsuden": {"id": "md/retsuden", "roms": ["Sangokushi Retsuden - Ransei no Eiyuutachi (Japan).zip",
                                              "San Guo Zhi Lie Zhuan - Luan Shi Qun Ying (China).zip"]},
    "royal": {"id": "koei/royal-md", "roms": ["Royal Blood (Japan).zip"]},
    "san2": {"id": "koei/san2-md", "fragments": ["mob_parts"], "roms": ["Sangokushi II (Japan).zip"]},
    "san3": {"id": "koei/san3-md", "extras": ["kaodata/mob_parts.png"],
             "roms": ["Sangokushi III (Japan).zip", "megacd/Sangokushi III (Japan).7z"]},
    "sgz5": {"id": "md/sgz5", "roms": ["San Guo Zhi V (China) (Unl).zip"]},
    "taikou": {"id": "koei/taikoh-md", "roms": ["Taikou Risshiden (Japan).zip"]},
    "teitoku": {"id": "koei/tk-md", "roms": ["Teitoku no Ketsudan (Japan).zip"]},
    "winning": {"id": "koei/winning-md", "roms": ["megacd/Winning Post (Japan).7z"]},
    "zenkoku": {"id": "koei/nobu2-md", "roms": ["Nobunaga no Yabou - Zenkoku Ban (Japan).zip",
                                               "Nobunaga's Ambition (USA).zip"]},
}

IMAGES = (".png", ".gif", ".jpg")


def cbz(src: str, dst: str) -> int:
    names = sorted(n for n in os.listdir(src) if n != ".DS_Store")
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as z:
        for n in names:
            z.write(os.path.join(src, n), n)
    return len(names)


def sha1_file(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def inner_sums(path: str, name: str) -> list[str]:
    """sha1 of each file inside a .zip or .7z."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            return [f"{hashlib.sha1(z.read(i)).hexdigest()}  {name}/{i.filename}" for i in z.infolist() if not i.is_dir()]
    if path.lower().endswith(".7z"):
        # one pass: 7zz writes every member to stdout in listing order, split by the listed sizes (a solid archive
        # would be decompressed again for each member if extracted one by one)
        listing = subprocess.run(["7zz", "l", "-slt", "-ba", path], check=True, capture_output=True, text=True).stdout
        members = []
        for block in listing.split("\n\n"):
            f = dict(line.split(" = ", 1) for line in block.splitlines() if " = " in line)
            if f.get("CRC"):    # directories have no CRC
                members.append((f["Path"], int(f["Size"])))
        p = subprocess.Popen(["7zz", "x", "-so", path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out = []
        for m, size in members:
            h = hashlib.sha1()
            while size:
                block = p.stdout.read(min(size, 1 << 20))
                if not block:
                    raise RuntimeError(f"7zz ended early in {path}: {m}")
                h.update(block)
                size -= len(block)
            out.append(f"{h.hexdigest()}  {name}/{m}")
        if p.stdout.read(1) or p.wait():
            raise RuntimeError(f"7zz output does not match the listing of {path}")
        return out
    return []


def archive_original(path: str, dst_dir: str, name: str) -> None:
    """Copy path to dst_dir/name and put its sha1 lines in dst_dir's SHA1SUMS.txt (name may contain a subfolder)."""
    os.makedirs(os.path.dirname(os.path.join(dst_dir, name)), exist_ok=True)
    dst = os.path.join(dst_dir, name)
    if not (os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(path) and sha1_file(dst) == sha1_file(path)):
        shutil.copy2(path, dst)
    lines = inner_sums(path, name) + [f"{sha1_file(path)}  {name}"]
    sums = os.path.join(dst_dir, "SHA1SUMS.txt")
    old = []
    if os.path.exists(sums):
        with open(sums, encoding="utf-8") as f:
            old = f.read().splitlines()
    keep = [x for x in old if x.split("  ", 1)[1] != name and not x.split("  ", 1)[1].startswith(name + "/")]
    with open(sums, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(keep + lines, key=lambda x: x.split("  ", 1)[1])) + "\n")


def is_kaodata(name: str) -> bool:
    return name.startswith("kaodata") or name.endswith("-md")


def copy_output(src: str, dst: str, fragments: list[str], top: bool = True) -> None:
    os.makedirs(dst, exist_ok=True)
    for name in sorted(os.listdir(src)):
        path = os.path.join(src, name)
        if os.path.isfile(path):
            if name != ".DS_Store":
                shutil.copy2(path, os.path.join(dst, name))
        elif name in fragments:
            print(f"  skip {name}/ (fragments)")
        elif top and is_kaodata(name):
            print(f"  skip {name}/ (kaodata dataset)")
        elif name == "portrait-sheet":
            os.makedirs(os.path.join(dst, "sheets"), exist_ok=True)
            for sheet in sorted(os.listdir(path)):
                out = os.path.join(path, sheet, "out")
                for page in sorted(os.listdir(out)) if os.path.isdir(out) else []:
                    shutil.copy2(os.path.join(out, page), os.path.join(dst, "sheets", page))
        elif all(n.lower().endswith(IMAGES) for n in os.listdir(path) if n != ".DS_Store"):
            print(f"  {name}.cbz: {cbz(path, os.path.join(dst, name + '.cbz'))} images")
        else:
            copy_output(path, os.path.join(dst, name), fragments, top=False)


def archive(game: str, library: str) -> None:
    cfg = GAMES[game]
    src = os.path.join(ROOT, game, "output")
    dst = os.path.join(library, cfg["id"])
    print(game, flush=True)
    copy_output(src, dst, cfg.get("fragments", []))
    for extra in cfg.get("extras", []):
        shutil.copy2(os.path.join(src, extra), os.path.join(dst, os.path.basename(extra)))
    cd = False
    for rom in cfg["roms"]:
        if rom.startswith("megacd/"):
            cd = True
            archive_original(os.path.join(ROMS, rom), os.path.join(library, "_original", "megacd"), rom[7:])
        else:
            archive_original(os.path.join(ROMS, rom), os.path.join(library, "_original", "md"), rom)
    if cd:
        for name in sorted(os.listdir(os.path.join(MEGACD, "bios"))):
            if name != ".DS_Store":
                archive_original(os.path.join(MEGACD, "bios", name), os.path.join(library, "_original", "megacd"),
                                 f"bios/{name}")
    print(f"  -> {dst}", flush=True)
    for need in [os.path.join(dst, "README.md"), os.path.join(library, cfg["id"].split("/")[0] + ".md")]:
        if not os.path.exists(need):
            print(f"  write by hand: {need}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--library", default=os.path.expanduser("~/game-library"))
    args = ap.parse_args()
    todo = sorted(GAMES) if args.all else args.games
    unknown = set(todo) - set(GAMES)
    if not todo or unknown:
        ap.error(f"games: {' '.join(sorted(GAMES))}" + (f"; unknown: {' '.join(sorted(unknown))}" if unknown else ""))
    for game in todo:
        archive(game, args.library)


if __name__ == "__main__":
    main()
