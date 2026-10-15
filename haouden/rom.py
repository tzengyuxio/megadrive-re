"""MD 信長の野望・覇王伝 (KOEI, 1993) ROM decoding.

Offsets are ROM offsets (= 68000 addresses); RAM addresses are $FF0000-based. Multi-byte values are big-endian.
Text is Shift-JIS, with three user-defined codes for 長宗我部 (LIGATURES). The record layouts follow the SFC
version (~/works/superfamicom-re/haouden) with 4-byte pointers and word alignment. See docs/ROM_FORMAT.md.
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from lz import decompress

DEFAULT_ROM = os.path.join(REPO, "roms", "Nobunaga no Yabou - Haouden (Japan).zip")

# Scenario images: the loader at $1E2EE copies 0x6F3A bytes of scenario s (pointer table SCENARIO_TABLE, index =
# scenario number 1-3) to $FF001A and the common block COMMON (0x522 bytes) to $FF6F54.
SCENARIO_COUNT = 3
SCENARIO_YEARS = [1551, 1568, 1582]
SCENARIO_TABLE = 0x74D44          # 4 long pointers, index 1-3 used
IMAGE_RAM, IMAGE_SIZE = 0xFF001A, 0x6F3A
COMMON, COMMON_RAM, COMMON_SIZE = 0x8D624, 0xFF6F54, 0x522
DAIMYO, DAIMYO_COUNT, DAIMYO_SIZE = 0xFF01BC, 64, 42
PERSONS, PERSON_COUNT, PERSON_SIZE = 0xFF0C3C, 460, 44
CASTLES, CASTLE_COUNT, CASTLE_SIZE = 0xFF5B4C, 110, 42
FUTURE = [0x82ECC, 0x85014, 0x85FC8]  # persons appearing later, 30-byte records, empty name ends
FUTURE_SIZE = 30
BIRTH_BASE = 1476
STATS = ["政治", "戦闘", "智謀", "采配", "野望"]

# String tables: long pointers to NUL-terminated Shift-JIS strings
STRING_TABLES = {"provinces": (0x5EBD6, 64), "titles": (0x5E66E, 226), "treasures": (0x5E9F6, 120),
                 "battles": (0x5EDA8, 15), "stat_names": (0x5CED2, 8), "princesses": (0x74D58, 93),
                 "terrains": (0x7B1DA, 15)}
CASTLE_XY = 0x76BFA        # 110 x (x, y) bytes: castle cell on the big map ($EF9A reads it)
BATTLE_CASTLES = 0x76FFC   # 15 words: castle of each historic battle ($27C7A)
SIEGE_TYPES = 0x5E320      # 110 words: castle family for the battle maps without a castle ($27DA2)
LIGATURES = {b"\xec\x8c\xec\x8d\xec\x8e": "長宗我部", b"\xec\x8f\xec\x8d\xec\x8e": "香宗我部"}

# Faces: 40x48 = 5x6 4bpp tiles row-major (960 bytes), built by $7056(x, y, face id) into a stack buffer and
# uploaded to VRAM tile $200. All LZ streams use the decoder at $3C36 (lz.py).
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
PORTRAITS, PORTRAIT_COUNT = 0x1112C6, 348   # long pointers to LZ streams ($7032)
FACE_TABLE = 0x728E0       # word per face id (used for 0xD3-0x36D): bit 15 = portrait (w & 0x7FFF), else code
FACE_TABLE2 = 0x72A3E      # word per face id - 0x36E (used for 0x37A-0x391): composite code
FACE_PARTS = [0x113A86, 0x116140, 0x11704A, 0x11776C, 0x1181FE]  # per part: long pointers, index group*5+v
FACE_PART_SHIFT = 0x5CCA8  # 5 words: part p takes code bits 3*shift .. 3*shift+2
FACE_PART_AT = 0x5CC58     # 8 groups x 5 words: first tile of part p
FACE_PALETTE = 0x5EE22     # 16 MD colours (CRAM line 1)
FACE_PART_COUNT, FACE_PART_VARIANTS = 5, 5
FACE_GROUPS = [0, 1, 2, 3, 4, 6]  # group numbers $6F44 returns (5 is never used)
FACE_ID_COUNT = 0x3A1             # face ids 0-0x3A0; 0x398, 0x399 not handled by the game
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def load_rom_bytes(path: str = DEFAULT_ROM) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            return z.read(next(n for n in z.namelist() if n.lower().endswith((".md", ".bin", ".gen"))))
    with open(path, "rb") as fh:
        return fh.read()


def be16(b: bytes, i: int) -> int:
    return b[i] << 8 | b[i + 1]


def be32(b: bytes, i: int) -> int:
    return int.from_bytes(b[i:i + 4], "big")


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


def decode_tile(raw: bytes) -> list[int]:
    """64 colour indices of a 4bpp 8x8 tile."""
    return [raw[i // 2] >> (4 if i % 2 == 0 else 0) & 15 for i in range(64)]


def text(raw: bytes) -> str:
    """Shift-JIS game string up to NUL, with the 長宗我部 ligatures."""
    raw = raw.split(b"\0")[0]
    for k, v in LIGATURES.items():
        raw = raw.replace(k, v.encode("cp932"))
    return raw.decode("cp932")


def face_group(fid: int) -> int:
    """Composite face group of a face id ($6F44)."""
    for g, hi in ((0, 0x160), (1, 0x1EC), (2, 0x278), (3, 0x304), (4, 0x36E)):
        if fid < hi:
            return g
    return 6


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self._lz: dict[int, bytes] = {}

    def lz(self, p: int) -> bytes:
        if p not in self._lz:
            self._lz[p] = decompress(self.data, p)[0]
        return self._lz[p]

    def string_table(self, name: str) -> list[str]:
        base, n = STRING_TABLES[name]
        return [text(self.data[be32(self.data, base + 4 * i):]) for i in range(n)]

    # --- scenarios ---
    def image(self, sc: int) -> bytes:
        """The scenario image as it lies in RAM from $FF0000 (bytes before $FF001A are 0)."""
        o = be32(self.data, SCENARIO_TABLE + 4 * (sc + 1))
        return bytes(IMAGE_RAM - 0xFF0000) + self.data[o:o + IMAGE_SIZE]

    def common(self) -> bytes:
        return self.data[COMMON:COMMON + COMMON_SIZE]

    def ram_image(self, sc: int) -> bytes:
        """RAM $FF0000-$FF7475 after the loader: image, common block, and for 1582 ($1E2D6) $FF72A4 |= 0x40,
        $FF72AC = 0xFF."""
        b = bytearray(self.image(sc) + self.common())
        if sc == 2:
            b[0x72A5] |= 0x40
            b[0x72AC] = 0xFF
        return bytes(b)

    def name(self, r: bytes) -> tuple[str, str]:
        return text(r[0:7]), text(r[7:14])

    def scenario_persons(self, sc: int, img: bytes | None = None) -> list[dict]:
        """460 slots of 44 bytes at $FF0C3C (empty names skipped)."""
        img = img or self.image(sc)
        out = []
        for k in range(PERSON_COUNT):
            a = PERSONS - 0xFF0000 + PERSON_SIZE * k
            r = img[a:a + PERSON_SIZE]
            if r[4] == 0:
                continue
            sur, given = self.name(r[4:18])
            p = {"slot": k, "addr": PERSONS + PERSON_SIZE * k, "raw": r, "next": be32(r, 0), "surname": sur,
                 "given": given, "born": BIRTH_BASE + r[18], "b24": r[24], "b25": r[25], "b26": r[26],
                 "b27": r[27], "castle": r[28], "b29": r[29], "b30": r[30], "loyalty": r[31], "kiai": r[32] & 15,
                 "b32_hi": r[32] >> 4, "id": be16(r, 34), "fiefs": be16(r, 36), "b38": r[38:41].hex(), "w42": be16(r, 42)}
            for i, s in enumerate(STATS):
                p[s] = r[19 + i]
            out.append(p)
        return out

    def future_persons(self, sc: int) -> list[dict]:
        p = FUTURE[sc]
        out = []
        while self.data[p + 4]:
            r = self.data[p:p + FUTURE_SIZE]
            sur, given = self.name(r[4:18])
            f = {"no": len(out), "raw": r, "year": BIRTH_BASE + r[0], "b1": r[1], "b2": r[2], "castle": r[3],
                 "surname": sur, "given": given, "born": BIRTH_BASE + r[18], "b24": r[24], "b25": r[25],
                 "id": be16(r, 26), "tail": r[28:30].hex()}
            for i, s in enumerate(STATS):
                f[s] = r[19 + i]
            out.append(f)
            p += FUTURE_SIZE
        return out

    def scenario_castles(self, sc: int, img: bytes | None = None) -> list[dict]:
        """110 castles of 42 bytes at $FF5B4C."""
        img = img or self.image(sc)
        out = []
        for k in range(CASTLE_COUNT):
            a = CASTLES - 0xFF0000 + CASTLE_SIZE * k
            r = img[a:a + CASTLE_SIZE]
            out.append({"id": k, "addr": CASTLES + CASTLE_SIZE * k, "raw": r, "head0": be32(r, 0),
                        "lord": be32(r, 4), "name": text(r[8:16]), "b16": r[16], "province": r[17],
                        "daimyo": be32(r, 18), "size": r[22] & 0x7F, "main": r[22] >> 7, "defense": r[23],
                        "kan": be16(r, 24), "b26": r[26], "people": r[27], "commerce": r[28], "training": r[29],
                        "soldiers": be16(r, 30), "money": be16(r, 32), "food": be16(r, 34), "guns": be16(r, 36),
                        "horses": be16(r, 38), "order": r[40], "b41": r[41]})
        return out

    def scenario_daimyo(self, sc: int, img: bytes | None = None) -> list[dict]:
        """64 daimyo slots of 42 bytes at $FF01BC (+0 = 0: empty)."""
        img = img or self.image(sc)
        out = []
        for k in range(DAIMYO_COUNT):
            a = DAIMYO - 0xFF0000 + DAIMYO_SIZE * k
            r = img[a:a + DAIMYO_SIZE]
            out.append({"slot": k, "addr": DAIMYO + DAIMYO_SIZE * k, "raw": r, "head": be32(r, 0), "b4": r[4],
                        "relations": r[5:36].hex(), "contribution": r[36], "b37": r[37], "b38": r[38],
                        "b39": r[39], "crest": r[40]})
        return out

    def scenario(self, sc: int, img: bytes | None = None) -> dict:
        """Persons, castles and daimyo of a scenario with the RAM pointers resolved."""
        persons = self.scenario_persons(sc, img)
        by_addr = {p["addr"]: p for p in persons}
        castles = self.scenario_castles(sc, img)
        daimyo = [d for d in self.scenario_daimyo(sc, img) if d["head"]]
        d_by_addr = {d["addr"]: d for d in daimyo}
        for c in castles:
            members, a = [], c["lord"]
            while a and len(members) < PERSON_COUNT:
                members.append(by_addr[a])
                a = by_addr[a]["next"]
            c["members"] = members
            c["daimyo_slot"] = d_by_addr[c["daimyo"]]["slot"] if c["daimyo"] else None
        for d in daimyo:
            d["head_person"] = by_addr[d["head"]]
            d["castles"] = [c for c in castles if c["daimyo"] == d["addr"]]
        return {"persons": persons, "castles": castles, "daimyo": daimyo}

    def person_master(self) -> dict[int, dict]:
        """Person id -> first record (scenario 1-3, then the later-appearing lists) plus every name used."""
        out: dict[int, dict] = {}
        for sc in range(SCENARIO_COUNT):
            for kind, recs in (("start", self.scenario_persons(sc)), ("future", self.future_persons(sc))):
                for r in recs:
                    m = out.setdefault(r["id"], {"id": r["id"], "first": r, "names": [], "appear": []})
                    n = r["surname"] + r["given"]
                    if n not in m["names"]:
                        m["names"].append(n)
                    m["appear"].append((sc, kind, r))
        return dict(sorted(out.items()))

    def castle_cells(self) -> list[tuple[int, int]]:
        return [(self.data[CASTLE_XY + 2 * i], self.data[CASTLE_XY + 2 * i + 1]) for i in range(CASTLE_COUNT)]

    def historic_battle_castles(self) -> list[int]:
        return [be16(self.data, BATTLE_CASTLES + 2 * i) for i in range(STRING_TABLES["battles"][1])]

    def siege_types(self) -> list[int]:
        return [be16(self.data, SIEGE_TYPES + 2 * i) for i in range(CASTLE_COUNT)]

    # --- faces ---
    def face_source(self, fid: int) -> tuple:
        """('portrait', n) or ('comp', group, code), as $7056 decides; None for 0x398-0x399 (not handled)."""
        if fid < 0xD3:
            return ("portrait", fid + 12)
        if fid < 0x36E:
            w = be16(self.data, FACE_TABLE + 2 * fid)
            return ("portrait", 12 + (w & 0x7FFF)) if w & 0x8000 else ("comp", face_group(fid), w)
        d = fid - 0x36E
        if d < 12:
            return ("portrait", d)
        if fid < 0x392:
            return ("comp", face_group(fid), be16(self.data, FACE_TABLE2 + 2 * d))
        if fid < 0x398:
            return ("portrait", fid - 0x24B)
        if 0x39A <= fid < FACE_ID_COUNT:
            return ("portrait", fid - 0x24D)
        return None

    def face_ids(self) -> list[int]:
        return [f for f in range(FACE_ID_COUNT) if self.face_source(f) is not None]

    def portrait_tiles(self, n: int) -> bytes:
        return self.lz(be32(self.data, PORTRAITS + 4 * n))[:FACE_BYTES]

    def face_part_at(self, g: int, p: int) -> int:
        """First tile of part p in group g."""
        return be16(self.data, FACE_PART_AT + 2 * (g * 5 + p))

    def face_part_tiles(self, g: int, p: int, v: int) -> bytes:
        """Tiles of variant v (0-4) of part p of group g."""
        return self.lz(be32(self.data, FACE_PARTS[p] + 4 * (g * 5 + v)))

    def part_variant(self, code: int, p: int) -> int:
        return code >> (3 * be16(self.data, FACE_PART_SHIFT + 2 * p)) & 7

    def composite(self, g: int, code: int) -> bytes:
        """960 bytes of a composed face: parts 0-4 written in order at their first tiles (later ones overwrite)."""
        buf = bytearray(FACE_BYTES)
        for p in range(FACE_PART_COUNT):
            raw = self.face_part_tiles(g, p, self.part_variant(code, p))
            a = self.face_part_at(g, p) * 32
            buf[a:a + len(raw)] = raw
        return bytes(buf[:FACE_BYTES])

    def face_tiles(self, fid: int) -> bytes:
        s = self.face_source(fid)
        return self.portrait_tiles(s[1]) if s[0] == "portrait" else self.composite(s[1], s[2])

    def face_palette(self) -> list[int]:
        return [be16(self.data, FACE_PALETTE + 2 * i) for i in range(16)]

    def face_rgb(self, fid: int) -> list[tuple[int, int, int]]:
        pal = [md_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(fid)]

    def face_pixels(self, fid: int = 0, tiles: bytes | None = None) -> list[int]:
        """40x48 colour indices, row-major."""
        tiles = tiles if tiles is not None else self.face_tiles(fid)
        w = FACE_W * 8
        out = [0] * (w * FACE_H * 8)
        for t in range(FACE_W * FACE_H):
            cx, cy = t % FACE_W * 8, t // FACE_W * 8
            for i, v in enumerate(decode_tile(tiles[t * 32:t * 32 + 32])):
                out[(cy + i // 8) * w + cx + i % 8] = v
        return out
