"""Put an original file (No-Intro zip, Redump .7z, BIOS) into the game library's _original/ and record its sha1, and
the sha1 of each file inside a .zip / .7z, in that folder's SHA1SUMS.txt (re-common §11: the only copy, read only).

Usage: .venv/bin/python scripts/add_rom.py FILE [FILE ...] [--to megacd/bios]
       .zip -> _original/md/, .7z -> _original/megacd/; --to names the folder under _original/ instead
A file already there with the same sha1 is not copied again; its SHA1SUMS.txt lines are rewritten.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from paths import ORIGINAL


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


def add(path: str, dst_dir: str, name: str) -> None:
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



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--to", help="folder under _original/, e.g. megacd/bios (default: md for .zip, megacd for .7z)")
    args = ap.parse_args()
    for path in args.files:
        to = args.to or ("megacd" if path.lower().endswith(".7z") else "md")
        top, _, sub = to.partition("/")
        name = os.path.join(sub, os.path.basename(path)) if sub else os.path.basename(path)
        add(path, os.path.join(ORIGINAL, top), name)
        print(f"{path} -> {os.path.join(ORIGINAL, top, name)}")


if __name__ == "__main__":
    main()
