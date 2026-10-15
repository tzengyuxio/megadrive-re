"""MD 信長の野望・武将風雲録 (KOEI, 1991) ROM decoding.

1 MB, no compression, big-endian. The game is C compiled; data tables are the SFC version's (superfamicom-re/bushou)
widened to 68000 C structs (16/32-bit fields, names stored inside the general records). See bushou/docs/ROM_FORMAT.md.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
from triage import load_rom

DEFAULT_ROM = os.path.join(REPO, "roms", "Nobunaga no Yabou - Bushou Fuuunroku (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

# ---------------------------------------------------------------- text
# 2-byte big-endian codes 0x8141 + g for font glyph g (the SFC code + 1, same 868 glyphs), half-width katakana
# (cp932 0xA1-0xDF) one byte each, 00 ends. Codes whose low byte is 00 are written 85F0/85F1/85F2 (= 8200/8300/
# 8400, e.g. 平 in 平野肩衝). Glyph g: 16x16 1bpp, 32 bytes at FONT + 32 g, 8x8 quarters TL TR BL BR, MSB left.
FONT = 0x50CA4
TEXT_BASE = 0x8141
GLYPH_COUNT = 868
ZERO_ESCAPE = 0x85F0
# Glyphs that hold 1.5 kanji each so that 3- and 4-kanji surnames fit (as in FC / SFC)
GAIJI = [((0x849C, 0x849D, 0x849E), "長宗我部"), ((0x849F, 0x849D, 0x849E), "香宗我部"),
         ((0x84A0, 0x84A1), "鳥屋尾"), ((0x84A2, 0x84A3), "佐々木")]

# ---------------------------------------------------------------- scenarios
# The game copies the whole block to RAM $FF1000 (memcpy at 0x50BA, 0x4254 bytes); the pointers inside are the low
# 16 bits of RAM addresses, so block offset = pointer - 0x1000.
RAM_BASE = 0x1000
BLOCK_SIZE = 0x4254
SCENARIOS = [  # name, block, start generals, later-general list
    ("戦国の動乱", 0x473B8, 250, 0x45AC2),
    ("信長包囲網", 0x4B60E, 255, 0x468F0),
]
HEADER = 0                      # +0 scenario number, +1 year - 1476, +2 month
PROVINCE_COUNT = 48
PROVINCE_START, PROVINCE_SIZE = 0x006, 72
NEXT_LATER = 0xD84              # copy of the next later-appearing general (30 bytes)
TEA_START, TEA_SIZE, TEA_COUNT = 0xDA2, 20, 48
DAIMYO_START, DAIMYO_SIZE, DAIMYO_SLOTS = 0x1162, 34, 48
GENERAL_START, GENERAL_SIZE, GENERAL_SLOTS = 0x17C2, 40, 272
LATER_SIZE = 30
BASE_YEAR = 1476

# ---------------------------------------------------------------- faces
# 40x48 = 5x6 MD tiles row-major (960 bytes). Dedicated face f (< 0x8000) at FACES + 960 f; composite pages
# follow the dedicated faces: head h page p at FACES + 960 (204 + 4h + p). Routines 0x793E / 0x7880.
FACES = 0x8EE68
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_COUNT = 204
COMPOSITE_FIRST = 204
COMPOSITE_HEADS = 8
# 8 heads x 11 BE longs: tilemap attribute (0x6000 = palette 3), then (first cell, count) of top, bottom, eyes,
# nose, mouth; the game copies the runs in that order from the page chosen by the code's 2-bit fields (third
# element of COMPOSITE_SLOTS = bit position in the face code).
COMPOSITE_AREAS = 0x5DB1E
COMPOSITE_SLOTS = [("top", "上", 3), ("bottom", "下", 5), ("eyes", "眼", 7), ("nose", "鼻", 9), ("mouth", "口", 11)]
PALETTES = 0x4F904              # CRAM palettes: map 0x4F904, face 0x4F964 (palette 3 of the province screen)
FACE_PALETTE = 0x4F964
MAP_PALETTE = 0x4F904
LEVELS = [0, 52, 87, 116, 144, 172, 206, 255]  # MD DAC levels as MAME renders them (screenshots match)

# ---------------------------------------------------------------- big map
# Daimyo-select / province map: plane B tilemap of 30 x 28 words at MAP_TILEMAP drawn at cell (1, 0), tiles from
# MAP_CHR loaded at VRAM tile 0x3FC, palette 0 (MAP_PALETTE).
MAP_CHR, MAP_CHR_TILE, MAP_CHR_COUNT = 0x80000, 0x3FC, 429
MAP_TILEMAP, MAP_W, MAP_H = 0x835A0, 30, 28

# ---------------------------------------------------------------- battle maps (same bytes as SFC)
FIELD_MAPS = 0x57904            # 48 x 154 bytes, 14 x 11 cells (column-odd hex rows), province order
CASTLE_MAPS = 0x5984C           # 49 x 143 bytes, 13 x 11 cells
CASTLE_LAYER = 0x5B558          # second layer of the castle maps, same shape
FIELD_W, CASTLE_W, BATTLE_H = 14, 13, 11
FIELD_COUNT, CASTLE_COUNT = 48, 49
FIELD_TERRAIN = {7: "平地", 8: "丘陵", 9: "林", 0xB: "海・湖", 0xC: "山", 0xD: "川"}
FIELD_NAMES, FIELD_NAME_COUNT = 0x5ED00, 49    # BE32 pointers to the battle names
CASTLE_NAMES, CASTLE_NAME_COUNT = 0x5EDC4, 50


def be16(raw: bytes, i: int) -> int:
    return raw[i] << 8 | raw[i + 1]


def be32(raw: bytes, i: int) -> int:
    return int.from_bytes(raw[i:i + 4], "big")


def load_charset(path: str = CHARSET) -> str:
    with open(path, encoding="utf-8") as f:
        cs = "".join(line.rstrip("\n") for line in f if not line.startswith("#"))
    assert len(cs) == GLYPH_COUNT, len(cs)
    return cs


def decode_tile(raw: bytes) -> list[int]:
    """One MD 4bpp tile (32 bytes, 4 bytes a row, high nibble left) -> 64 colour numbers, row-major."""
    return [raw[i // 2] >> (4 if i % 2 == 0 else 0) & 15 for i in range(64)]


def md_rgb(c: int) -> tuple[int, int, int]:
    """MD CRAM word (0000 BBB0 GGG0 RRR0) -> 8-bit RGB with MAME's DAC levels."""
    return LEVELS[c >> 1 & 7], LEVELS[c >> 5 & 7], LEVELS[c >> 9 & 7]


def is_composite(code: int) -> bool:
    return bool(code & 0x8000)


def decode_face_code(code: int) -> tuple[int, list[int]]:
    """Composite face code -> (head, page per slot in COMPOSITE_SLOTS order)."""
    return code & 7, [code >> bit & 3 for _, _, bit in COMPOSITE_SLOTS]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom(path)
        self.charset = load_charset()

    # ------------------------------------------------------------ text

    def codes(self, raw: bytes) -> list[int]:
        """Text bytes -> codes (2-byte glyph codes and 1-byte kana), up to 00."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            if 0x81 <= raw[i] < 0xA0 and i + 1 < len(raw):
                c = raw[i] << 8 | raw[i + 1]
                if ZERO_ESCAPE <= c < ZERO_ESCAPE + 3:
                    c = 0x8200 + (c - ZERO_ESCAPE) * 0x100
                out.append(c)
                i += 2
            else:
                out.append(raw[i])
                i += 1
        return out

    def text(self, raw: bytes) -> str:
        cs = self.codes(raw)
        out, i = [], 0
        while i < len(cs):
            for seq, s in GAIJI:
                if tuple(cs[i:i + len(seq)]) == seq:
                    out.append(s)
                    i += len(seq)
                    break
            else:
                c = cs[i]
                if c < 0x100:
                    out.append(bytes([c]).decode("cp932", "replace"))
                else:
                    out.append(self.charset[c - TEXT_BASE] if TEXT_BASE <= c < TEXT_BASE + GLYPH_COUNT else "〓")
                i += 1
        return "".join(out)

    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g (code 0x8141 + g)."""
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    # ------------------------------------------------------------ scenarios

    def block(self, s: int) -> int:
        return SCENARIOS[s][1]

    def scenario_info(self, s: int) -> dict:
        b = self.block(s)
        return {"name": SCENARIOS[s][0], "number": self.data[b], "year": BASE_YEAR + self.data[b + 1],
                "month": self.data[b + 2]}

    def general_index(self, ptr: int) -> int:
        return (ptr - RAM_BASE - GENERAL_START) // GENERAL_SIZE

    def general_record(self, s: int, i: int) -> bytes:
        o = self.block(s) + GENERAL_START + GENERAL_SIZE * i
        return self.data[o:o + GENERAL_SIZE]

    def generals(self, s: int) -> list[dict]:
        """Generals present at the start of scenario s (slots 0 .. start count - 1)."""
        info = self.scenario_info(s)
        out = []
        for i in range(SCENARIOS[s][2]):
            r = self.general_record(s, i)
            birth = BASE_YEAR + r[18]
            out.append({"index": i, "family": self.text(r[4:11]), "given": self.text(r[11:18]),
                        "name": self.text(r[4:11]) + self.text(r[11:18]), "birth": birth, "age": info["year"] - birth,
                        "politics": r[19], "war": r[20], "culture": r[21], "charm": r[22], "ambition": r[23],
                        "b24": r[24], "face_code": be16(r, 28), "flags": r[30], "b31": r[31], "b32": r[32],
                        "province": r[33], "daimyo": r[34], "loyalty": r[35], "next": be16(r, 2),
                        "b0": be16(r, 0)})
        return out

    def later_generals(self, s: int) -> list[dict]:
        """Generals that appear during scenario s (30-byte records, 00 ends)."""
        o, out = SCENARIOS[s][3], []
        while self.data[o] != 0:
            r = self.data[o:o + LATER_SIZE]
            out.append({"index": len(out), "appear": BASE_YEAR + r[0], "province": None if r[1] == 0xFF else r[1],
                        "b2": r[2], "family": self.text(r[3:10]), "given": self.text(r[10:17]),
                        "name": self.text(r[3:10]) + self.text(r[10:17]), "birth": BASE_YEAR + r[17],
                        "politics": r[18], "war": r[19], "culture": r[20], "charm": r[21], "ambition": r[22],
                        "b24": r[23], "face_code": be16(r, 26), "flags": r[28], "b29": r[29], "offset": o})
            o += LATER_SIZE
        return out

    def province_record(self, s: int, p: int) -> bytes:
        o = self.block(s) + PROVINCE_START + PROVINCE_SIZE * p
        return self.data[o:o + PROVINCE_SIZE]

    def province_names(self) -> list[str]:
        return [self.text(self.province_record(0, p)[6:12]) for p in range(PROVINCE_COUNT)]

    def province_neighbours(self, p: int) -> list[tuple[int, int]]:
        """(province, high 2 bits) per neighbour."""
        out = []
        for b in self.province_record(0, p)[50:57]:
            if b == 0xFF:
                break
            out.append((b & 0x3F, b >> 6))
        return out

    def provinces(self, s: int) -> list[dict]:
        names = self.province_names()
        out = []
        for p in range(PROVINCE_COUNT):
            r = self.province_record(s, p)
            dptr = be16(r, 48)
            owner = (dptr - RAM_BASE - DAIMYO_START) // DAIMYO_SIZE if dptr else None
            members, ptr = [], be16(r, 0)
            while ptr:
                g = self.general_index(ptr)
                members.append(g)
                ptr = be16(self.general_record(s, g), 2)
            out.append({"index": p, "name": names[p], "owner": owner, "gold": be32(r, 12), "rice": be32(r, 16),
                        "kokudaka": be32(r, 20), "flood": r[24], "town": be32(r, 26), "culture": r[30],
                        "tech": be32(r, 32), "people_loyalty": r[36], "castle": be16(r, 40), "soldiers": be32(r, 58),
                        "guns": be32(r, 62), "training": r[66], "soldier_loyalty": r[67], "generals": members,
                        "ptr2": be32(r, 2), "w42": be16(r, 42), "w44": be16(r, 44), "w46": be16(r, 46),
                        "w68": be16(r, 68), "w70": be16(r, 70)})
        return out

    def daimyos(self, s: int) -> list[dict]:
        gens = self.generals(s)
        out = []
        for d in range(DAIMYO_SLOTS):
            o = self.block(s) + DAIMYO_START + DAIMYO_SIZE * d
            r = self.data[o:o + DAIMYO_SIZE]
            if not be16(r, 2):
                continue
            g = self.general_index(be16(r, 2))
            rel = [(r[7 + k // 2] >> (4 * (1 - k % 2))) & 15 for k in range(DAIMYO_SLOTS)]
            out.append({"index": d, "general": g, "name": gens[g]["name"], "allies": [x for x in r[4:7] if x != 0xFF],
                        "relations": rel, "b31": r[31], "b32": r[32], "number": r[33]})
        return out

    def tea(self, s: int) -> list[dict]:
        gens = self.generals(s)
        out = []
        for t in range(TEA_COUNT):
            o = self.block(s) + TEA_START + TEA_SIZE * t
            r = self.data[o:o + TEA_SIZE]
            holder = be16(r, 16)
            g = self.general_index(holder) if holder else None
            out.append({"index": t, "name": self.text(r[:14]), "holder": g,
                        "holder_name": gens[g]["name"] if g is not None and g < len(gens) else "",
                        "value": r[18], "w14": be16(r, 14)})
        return out

    # ------------------------------------------------------------ faces

    def palette(self, offset: int) -> list[int]:
        return [be16(self.data, offset + 2 * i) for i in range(16)]

    def face_palette(self) -> list[int]:
        return self.palette(FACE_PALETTE)

    def portrait_tiles(self, f: int) -> bytes:
        o = FACES + FACE_BYTES * f
        return self.data[o:o + FACE_BYTES]

    def composite_page(self, head: int, page: int) -> bytes:
        return self.portrait_tiles(COMPOSITE_FIRST + 4 * head + page)

    def composite_table(self, head: int) -> list[int]:
        o = COMPOSITE_AREAS + 44 * head
        return [be32(self.data, o + 4 * i) for i in range(11)]

    def composite_runs(self, head: int) -> dict[str, list[int]]:
        """Cells copied for each slot (the table's (first, count) pairs)."""
        t = self.composite_table(head)
        return {sid: list(range(t[1 + 2 * k], t[1 + 2 * k] + t[2 + 2 * k])) for k, (sid, _, _) in enumerate(COMPOSITE_SLOTS)}

    def face_tiles(self, code: int) -> bytes:
        """960 bytes of the face the game builds for a face code."""
        if not is_composite(code):
            return self.portrait_tiles(code)
        head, pages = decode_face_code(code & 0x1FFF)
        buf = bytearray(FACE_BYTES)
        runs = self.composite_runs(head)
        for (sid, _, _), p in zip(COMPOSITE_SLOTS, pages):
            page = self.composite_page(head, p)
            for cell in runs[sid]:
                buf[32 * cell:32 * cell + 32] = page[32 * cell:32 * cell + 32]
        return bytes(buf)

    def face_pixels(self, code: int) -> list[int]:
        """40x48 colour numbers."""
        tiles = self.face_tiles(code)
        out = [0] * (40 * 48)
        for cell in range(30):
            px = decode_tile(tiles[32 * cell:32 * cell + 32])
            cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
            for i, v in enumerate(px):
                out[(cy + i // 8) * 40 + cx + i % 8] = v
        return out

    def face_rgb(self, code: int) -> list[tuple[int, int, int]]:
        pal = [md_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(code)]

    # ------------------------------------------------------------ big map

    def map_entries(self) -> list[int]:
        return [be16(self.data, MAP_TILEMAP + 2 * i) for i in range(MAP_W * MAP_H)]

    def map_tile(self, n: int) -> bytes:
        k = n - MAP_CHR_TILE
        assert 0 <= k < MAP_CHR_COUNT, hex(n)
        return self.data[MAP_CHR + 32 * k:MAP_CHR + 32 * k + 32]

    def map_rgb(self) -> tuple[int, int, list[tuple[int, int, int]]]:
        """(w, h, pixels) of the map (30 x 28 cells); colour 0 is drawn as palette colour 0."""
        pal = [md_rgb(c) for c in self.palette(MAP_PALETTE)]
        w, h = MAP_W * 8, MAP_H * 8
        out = [(0, 0, 0)] * (w * h)
        for i, e in enumerate(self.map_entries()):
            px = decode_tile(self.map_tile(e & 0x7FF))
            hf, vf = e >> 11 & 1, e >> 12 & 1
            cx, cy = i % MAP_W * 8, i // MAP_W * 8
            for k, v in enumerate(px):
                x, y = k % 8, k // 8
                if hf:
                    x = 7 - x
                if vf:
                    y = 7 - y
                out[(cy + y) * w + cx + x] = pal[v]
        return w, h, out

    # ------------------------------------------------------------ battle maps

    def battle_terrain(self, castle: bool, n: int) -> bytes:
        if castle:
            return self.data[CASTLE_MAPS + 143 * n:CASTLE_MAPS + 143 * (n + 1)]
        return self.data[FIELD_MAPS + 154 * n:FIELD_MAPS + 154 * (n + 1)]

    def castle_layer(self, n: int) -> bytes:
        return self.data[CASTLE_LAYER + 143 * n:CASTLE_LAYER + 143 * (n + 1)]

    def battle_names(self) -> tuple[list[str], list[str]]:
        def names(table: int, count: int) -> list[str]:
            return [self.text(self.data[be32(self.data, table + 4 * i):][:20]) for i in range(count)]
        return names(FIELD_NAMES, FIELD_NAME_COUNT), names(CASTLE_NAMES, CASTLE_NAME_COUNT)
