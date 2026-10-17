#!/usr/bin/env python3
"""Mega-CD images (Redump .7z / .zip with a .cue and Track 01 MODE1/2352): the data track's 2048-byte sectors and
its ISO 9660 files. Archives are read with bsdtar (libarchive, macOS built-in); the data track is cached under
roms/megacd/.cache/ as a plain 2048-byte-sector .iso, and cue() unpacks the bin/cue there for MAME.

Usage: .venv/bin/python tools/megacd.py IMAGE [--extract DIR]    # list the files (and copy them to DIR)
"""
import argparse
import os
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, "roms", "megacd", ".cache")
SECTOR = 2048


def is_image(path: str) -> bool:
    return path.lower().endswith(".7z")


def cue(path: str) -> str:
    """A single-file .cue/.bin of an image for MAME, which misreads Redump's one-file-per-track cue sheets: the
    tracks are joined once under the cache and the cue rewritten with absolute MSF times."""
    stem = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(CACHE, stem)
    single = os.path.join(out, "single.cue")
    if os.path.exists(single):
        return single
    os.makedirs(out, exist_ok=True)
    subprocess.run(["bsdtar", "-xf", path, "-C", out], check=True)
    with open(os.path.join(out, stem + ".cue"), encoding="ascii") as f:
        lines = f.read().splitlines()
    sheet, frames = ['FILE "single.bin" BINARY'], 0
    with open(os.path.join(out, "single.bin"), "wb") as joined:
        for line in lines:
            word = line.split()
            if word[0] == "FILE":
                name = line.split('"')[1]
                with open(os.path.join(out, name), "rb") as track:
                    frames = joined.tell() // 2352
                    joined.write(track.read())
                os.remove(os.path.join(out, name))
            elif word[0] == "TRACK":
                sheet.append(f"  {line.strip()}")
            elif word[0] == "INDEX":
                m, s, fr = map(int, word[2].split(":"))
                t = frames + (m * 60 + s) * 75 + fr
                sheet.append(f"    INDEX {word[1]} {t // 4500:02d}:{t // 75 % 60:02d}:{t % 75:02d}")
    with open(single, "w", encoding="ascii") as f:
        f.write("\n".join(sheet) + "\n")
    return single


def data_track(path: str) -> bytes:
    """User data (2048 bytes per sector) of Track 01."""
    iso = os.path.join(CACHE, os.path.splitext(os.path.basename(path))[0] + ".iso")
    if not os.path.exists(iso):
        names = subprocess.run(["bsdtar", "-tf", path], capture_output=True, text=True, check=True).stdout.split("\n")
        raw = subprocess.run(["bsdtar", "-xOf", path, next(n for n in names if n.endswith("(Track 01).bin"))],
                             capture_output=True, check=True).stdout
        assert len(raw) % 2352 == 0 and raw[15] == 1, "Track 01 is not MODE1/2352"
        os.makedirs(CACHE, exist_ok=True)
        with open(iso, "wb") as f:
            f.write(b"".join(raw[i + 16:i + 16 + SECTOR] for i in range(0, len(raw), 2352)))
    with open(iso, "rb") as f:
        return f.read()


def files(iso: bytes) -> dict[str, tuple[int, int]]:
    """ISO 9660 path -> (start sector, size), walking the directory records from the primary volume descriptor."""
    pvd = iso[16 * SECTOR:17 * SECTOR]
    assert pvd[1:6] == b"CD001", "no ISO 9660 volume"
    out = {}

    def walk(lba: int, size: int, prefix: str) -> None:
        d, i = iso[lba * SECTOR:lba * SECTOR + size], 0
        while i < len(d):
            n = d[i]
            if n == 0:  # records do not cross sectors
                i = (i // SECTOR + 1) * SECTOR
                continue
            start, length, flags = int.from_bytes(d[i + 2:i + 6], "little"), int.from_bytes(d[i + 10:i + 14], "little"), d[i + 25]
            name = d[i + 33:i + 33 + d[i + 32]]
            if name not in (b"\0", b"\1"):
                name = name.decode("ascii").split(";")[0]
                if flags & 2:
                    walk(start, length, prefix + name + "/")
                else:
                    out[prefix + name] = (start, length)
            i += n

    root = pvd[156:190]
    walk(int.from_bytes(root[2:6], "little"), int.from_bytes(root[10:14], "little"), "")
    return out


def read(iso: bytes, entry: tuple[int, int]) -> bytes:
    start, size = entry
    return iso[start * SECTOR:start * SECTOR + size]


def main() -> None:
    ap = argparse.ArgumentParser(description="列出 Mega-CD 映像資料軌的 ISO 9660 檔案")
    ap.add_argument("image")
    ap.add_argument("--extract", help="把檔案複製到這個目錄")
    args = ap.parse_args()
    iso = data_track(args.image)
    print(f"system area: {iso[0:16].decode('ascii', 'replace')} / {iso[0x100:0x110].decode('ascii', 'replace')} "
          f"/ {iso[0x180:0x18E].decode('ascii', 'replace')}")
    for name, (start, size) in files(iso).items():
        print(f"{start:6d} {size:9d}  {name}")
        if args.extract:
            os.makedirs(os.path.dirname(os.path.join(args.extract, name)) or args.extract, exist_ok=True)
            with open(os.path.join(args.extract, name), "wb") as f:
                f.write(read(iso, (start, size)))


if __name__ == "__main__":
    main()
