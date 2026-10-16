"""MD 太閤立志伝 Taikou Risshiden (KOEI, 1993) ROM decoding.

Offsets are file offsets of the 1.25 MB ROM (= 68000 addresses). See docs/ROM_FORMAT.md. The data is the SFC
version's (superfamicom-re/taikou) with 16-bit fields big-endian and word-aligned, so most records grew by a few
padding bytes. Text is Shift-JIS (half-width punctuation). Portraits are KOEI LZ, decoded by the table-free
decoder of haouden/lz.py (the game's decoder is $33BA).
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.append(os.path.join(REPO, "haouden"))  # last, so haouden/verify_*.py never shadow ours
import lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Taikou Risshiden (Japan).zip")

# Names: 716 x 16 bytes: +0 surname (7 bytes SJIS, 0-padded), +7 given name (7), +14 face code BE16.
# The name index is the person id (person record +0); names 713-715 have no person record.
NAMES, NAME_SIZE, NAME_COUNT = 0x85D22, 16, 716

# Start of game: $17D?? clears and fills these RAM areas (memmove $7014; the first with the word copy $7048).
# It runs at power-on and again for a new game; (ROM, RAM, size).
INIT_SEGMENTS = [(0x7A8B0, 0xFF0040, 0x140), (0x7A9F0, 0xFF0180, 0x50), (0x7AA40, 0xFF01D0, 0x78),
                 (0x85A7A, 0xFF0248, 0x2A8), (0x7B35E, 0xFF04F0, 0x387C), (0x7AAB8, 0xFF3D6C, 0x8A6)]
FACTIONS, FACTION_SIZE, FACTION_COUNT = 0x85A7A, 34, 20          # RAM $FF0248
PERSONS, PERSON_SIZE, PERSON_COUNT = 0x7B35E, 60, 241            # RAM $FF04F0; persons present at the start
LATER_PERSONS, LATER_COUNT = 0x7EBDA, 472                        # the persons who appear later (right after)
PERSON_TOTAL = PERSON_COUNT + LATER_COUNT                        # 713
CASTLE_STATES, CASTLE_STATE_SIZE, CASTLE_STATE_COUNT = 0x7AAB8, 18, 123   # RAM $FF3D6C
FACTION_RAM, PERSON_RAM, CASTLE_STATE_RAM = 0xFF0248, 0xFF04F0, 0xFF3D6C
CASTLES, CASTLE_SIZE, CASTLE_COUNT = 0x77952, 20, 125
MAP_W = 41                                                       # castle location = block y * 41 + block x

STATS = ["外交", "内政", "魅力", "統率", "武力", "野心"]  # person +39..+44
SKILL_GRADES = "DCBA"                    # skill level 0-3 as the info screen shows it
# String tables: 4-byte pointers to NUL-terminated strings
STRING_TABLES = {"ranks": (0x761E8, 9), "skills": (0x7839A, 8), "stat_names": (0x78382, 6),
                 "formations": (0x78336, 7), "positions": (0x78352, 5), "weather": (0x78366, 4),
                 "units": (0x78376, 3)}

# Faces: $E36E(x, y, code, slot) draws a 32x40 face (4x5 4bpp tiles, row-major) to VRAM tile 0x260 + 20 slot
# and puts it on plane A with palette line 0 (FACE_PALETTE, loaded with the screen).
#   code bit 15 = 0: portrait code ($E2F0): KOEI LZ at the pointer PORTRAITS + 4 code (258 portraits).
#   code bit 15 = 1: composite ($E266 -> $E136): type t = bits 8-11 (0-11). COMP_RUNS + 20 t: 5 (first tile,
#     tile count) BE16 pairs; COMP_PTRS + 80 t: 5 x 4 pointers (part p, variant v) to raw tiles. Build order:
#     part 4 with variant bits 0-1, part 0 bits 6-7, part 1 bits 4-5, part 2 bits 2-3, part 3 bits 2-3 (parts 2
#     and 3 share bits 2-3); each copies its run of whole tiles into the face, later ones over earlier ones.
FACE_W, FACE_H = 4, 5
FACE_BYTES = 640
PORTRAITS, PORTRAIT_COUNT = 0x10AFD8, 258
COMP_PTRS, COMP_RUNS = 0xD2BFE, 0xD2FBE
COMP_TYPES, COMP_PARTS, COMP_VARIANTS = 12, 5, 4
COMP_ORDER = [(4, 0), (0, 6), (1, 4), (2, 2), (3, 2)]   # (part, shift of its 2 variant bits) in build order
FACE_PALETTE = 0x8A2C0
FACE_VRAM_TILE = 0x260
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


def be16(raw: bytes, i: int) -> int:
    return raw[i] << 8 | raw[i + 1]


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            return z.read(z.namelist()[0])
    with open(path, "rb") as f:
        return f.read()


def sjis(raw: bytes) -> str:
    """Shift-JIS up to NUL; half-width kana / punctuation become full width."""
    s = raw.split(b"\0", 1)[0].decode("cp932", "replace")
    s = "".join(unicodedata.normalize("NFKC", c) if "｡" <= c <= "ﾟ" else c for c in s)
    return unicodedata.normalize("NFC", s)


def is_composite(code: int) -> bool:
    return bool(code & 0x8000)


def composite_parts(code: int) -> tuple[int, list[int]]:
    """(type, [variant of part 0-4]) of a composite face code."""
    v = {p: code >> s & 3 for p, s in COMP_ORDER}
    return code >> 8 & 15, [v[p] for p in range(COMP_PARTS)]


def tiles_pixels(tiles: bytes, w: int = FACE_W, h: int = FACE_H) -> list[int]:
    """MD 4bpp tiles (row-major, w x h) -> colour numbers, row-major."""
    out = [0] * (w * h * 64)
    for t in range(w * h):
        tx, ty = t % w * 8, t // w * 8
        for i in range(64):
            b = tiles[32 * t + i // 2]
            out[(ty + i // 8) * w * 8 + tx + i % 8] = b >> 4 if i % 2 == 0 else b & 15
    return out


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)

    def u32(self, o: int) -> int:
        return int.from_bytes(self.data[o:o + 4], "big")

    def cstring(self, p: int) -> str:
        return sjis(self.data[p:self.data.index(b"\0", p) + 1])

    def string_table(self, name: str) -> list[str]:
        base, n = STRING_TABLES[name]
        return [self.cstring(self.u32(base + 4 * i)) for i in range(n)]

    # --- names ---
    def names(self) -> list[dict]:
        """716 name entries: id, surname, given name, face code."""
        out = []
        for i in range(NAME_COUNT):
            r = self.data[NAMES + NAME_SIZE * i:NAMES + NAME_SIZE * (i + 1)]
            out.append({"id": i, "surname": sjis(r[0:7]), "given": sjis(r[7:14]), "face": be16(r, 14)})
        return out

    # --- start of game ---
    def init_image(self, ram: int, size: int) -> bytes:
        """What the start-of-game copies leave in RAM [ram, ram + size) (None where nothing is copied)."""
        out = [None] * size
        for rom, dst, n in INIT_SEGMENTS:
            for i in range(n):
                if ram <= dst + i < ram + size:
                    out[dst + i - ram] = self.data[rom + i]
        return out

    def person_record(self, k: int) -> bytes:
        """60-byte record k (0-240 from the start data, 241-712 from LATER_PERSONS)."""
        o = PERSONS + PERSON_SIZE * k if k < PERSON_COUNT else LATER_PERSONS + PERSON_SIZE * (k - PERSON_COUNT)
        return self.data[o:o + PERSON_SIZE]

    def persons(self) -> list[dict]:
        """713 person records. See docs/ROM_FORMAT.md §5."""
        names = self.names()
        out = []
        for k in range(PERSON_TOTAL):
            r = self.person_record(k)
            pid = be16(r, 0)
            n = names[pid]
            p = {"record": k, "id": pid, "raw": r, "surname": n["surname"], "given": n["given"], "face": n["face"],
                 "start": k < PERSON_COUNT, "positions": [(be16(r, 2 + 4 * i), r[4 + 4 * i], r[5 + 4 * i])
                                                          for i in range(3)],
                 "faction": r[26], "castle": r[27], "rank": r[28], "w30": be16(r, 30), "b32": r[32], "b33": r[33],
                 "政略Lv": r[34], "b35": r[35], "b36": r[36], "戦術Lv": r[38],
                 "skills": [r[45] >> (6 - 2 * i) & 3 for i in range(4)] + [r[46] >> (6 - 2 * i) & 3 for i in range(3)],
                 "tail": r[47:51] + r[52:60]}
            for i, s in enumerate(STATS):
                p[s] = r[39 + i]
            p["skills"].append(sum(p["skills"]) // 7)   # 文化 = mean of the other seven (as in the SFC version)
            out.append(p)
        return out

    def factions(self) -> list[dict]:
        """20 factions of 34 bytes: +0 daimyo record (FF = none), +1..+20 one byte per faction (unsolved, 0 for
        itself), +21 home castle (presumed), +22 BE16, +24 / +26 BE16 / +28..+33 unsolved."""
        out = []
        for k in range(FACTION_COUNT):
            r = self.data[FACTIONS + FACTION_SIZE * k:FACTIONS + FACTION_SIZE * (k + 1)]
            out.append({"id": k, "raw": r, "daimyo": r[0], "relations": list(r[1:21]), "castle": r[21],
                        "w22": be16(r, 22), "b24": r[24], "w26": be16(r, 26), "tail": r[28:34]})
        return out

    def castles(self) -> list[dict]:
        """125 castles (static table) joined with their start-of-game state (18 bytes each; castles 123 安土 and
        124 大坂 have no state record at the start)."""
        out = []
        for k in range(CASTLE_COUNT):
            r = self.data[CASTLES + CASTLE_SIZE * k:CASTLES + CASTLE_SIZE * (k + 1)]
            loc = be16(r, 14)
            c = {"id": k, "raw": r, "name": sjis(r[0:9]), "neighbours": [b for b in r[9:13] if b != 0xFF],
                 "location": loc, "block": (loc % MAP_W, loc // MAP_W), "cell": (r[16], r[17]), "b18": r[18],
                 "state": None}
            if k < CASTLE_STATE_COUNT:
                o = CASTLE_STATES + CASTLE_STATE_SIZE * k
                s = self.data[o:o + CASTLE_STATE_SIZE]
                c.update({"state": s, "lord": s[1], "faction": s[2], "s3": s[3], "s4": s[4], "s6": be16(s, 6),
                          "s8": be16(s, 8), "s10": s[10], "s11": s[11], "s12": be16(s, 12), "s14": s[14],
                          "s15": s[15], "s16": s[16]})
            out.append(c)
        return out

    # --- faces ---
    def portrait_raw(self, n: int) -> bytes:
        return lz.decompress(self.data, self.u32(PORTRAITS + 4 * n))[0][:FACE_BYTES]

    def composite_runs(self, t: int) -> list[tuple[int, int]]:
        """(first tile, tile count) of parts 0-4 of type t."""
        o = COMP_RUNS + 20 * t
        return [(be16(self.data, o + 4 * p), be16(self.data, o + 4 * p + 2)) for p in range(COMP_PARTS)]

    def composite_part(self, t: int, p: int, v: int) -> tuple[int, bytes]:
        """(first tile, tiles) that variant v of part p of type t writes."""
        first, count = self.composite_runs(t)[p]
        src = self.u32(COMP_PTRS + 80 * t + 16 * p + 4 * v)
        return first, self.data[src:src + 32 * count]

    def face_raw(self, code: int, base: bytes = bytes(FACE_BYTES)) -> bytes:
        """640 bytes of tiles the game builds for a face code. A composite face only writes its parts' tiles over
        the buffer (`base`; the game doesn't clear it, but the parts of every type cover all 20 tiles)."""
        if not is_composite(code):
            return self.portrait_raw(code)
        t, parts = composite_parts(code)
        buf = bytearray(base)
        for p, _ in COMP_ORDER:
            first, tiles = self.composite_part(t, p, parts[p])
            buf[32 * first:32 * first + len(tiles)] = tiles
        return bytes(buf)

    def face_pixels(self, code: int) -> list[int]:
        return tiles_pixels(self.face_raw(code))

    def face_palette(self) -> list[int]:
        return [be16(self.data, FACE_PALETTE + 2 * i) for i in range(16)]

    def face_rgb(self, code: int) -> list[tuple[int, int, int]]:
        pal = [md_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(code)]
