"""MD 三國志III (KOEI, 1992) ROM decoding.

Offsets are file offsets of the 1.5 MB image (68000 address = file offset). See docs/ROM_FORMAT.md. The game is
compiled C, and its tables are the SFC version's (~/works/superfamicom-re/san3) with 16-bit fields big-endian,
padding bytes for word alignment and Shift-JIS text instead of the SFC's own character codes.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import lz
from triage import load_rom

DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Sangokushi III (Japan).zip")

# Font ($C4EE): 0x867 sorted Shift-JIS codes at FONT_CODES; glyph i (binary search, $C4A0) is 32 bytes at
# FONT_GLYPHS + 32 i = four 8x8 1bpp tiles (top-left, top-right, bottom-left, bottom-right). Half-width
# characters ($C3A2): 8x16, 16 bytes at FONT_HALF + 16 * (code - 0x20).
FONT_CODES = 0x74C00
FONT_COUNT = 0x867
FONT_GLYPHS = 0x63F40
FONT_HALF = 0x63C40
# Gaiji: codes 0xEB9F-0xEBDB are characters outside JIS X 0208 (names); read off the glyphs, matching the
# characters the SFC version uses in the same names.
GAIJI = dict(zip(
    [0xEB9F, 0xEBA0, 0xEBA1, 0xEBA2, 0xEBA3, 0xEBA4, 0xEBA5, 0xEBA6, 0xEBA7, 0xEBA8, 0xEBA9, 0xEBAB, 0xEBAC,
     0xEBAD, 0xEBAE, 0xEBAF, 0xEBB0, 0xEBB1, 0xEBB2, 0xEBB3, 0xEBB4, 0xEBB5, 0xEBB6, 0xEBB7, 0xEBB8, 0xEBB9,
     0xEBBA, 0xEBBB, 0xEBBC, 0xEBBF, 0xEBC0, 0xEBC4, 0xEBC6, 0xEBC8, 0xEBC9, 0xEBCC, 0xEBCE, 0xEBD0, 0xEBD1,
     0xEBD2, 0xEBD3, 0xEBD4, 0xEBD5, 0xEBD6, 0xEBD7, 0xEBD8, 0xEBD9, 0xEBDB],
    "瓚昱彧郃蒯蔡傕邕汜詡鄧龐繇邈騭畯闞玠顗邢歆闓禕譙琬郝琮伷褚邳琦璝彤釭涪鄴臧莒綝諶惲昕琪笮祜蕤璜晙"))

SCENARIO_COUNT = 6
# Scenario header ($1B76E): 34 bytes per scenario -> $FF0788 (SFC 33 bytes + 1 pad, year BE)
SCENARIO_HEADER = 0x81BB6
HEADER_SIZE = 34
SCENARIO_TITLES = 0x8C3C8   # 6 long pointers to the titles

# Persons 0-531 (sorted by reading): 30 bytes, read from ROM directly
PERSONS = 0x78E94
PERSON_COUNT = 532
PERSON_SIZE = 30
# Scenario tables: 6 long pointers each
SCEN_PERSON_PTRS = 0x8C620   # 531 x 4 bytes -> $FF1562 + 30 i ($1B95A)
SCEN_PROVINCE_PTRS = 0x8C638  # 46 x 32 bytes -> $FF07C4 + 52 k ($1BA6C)
SCEN_FACTION_PTRS = 0x8C650  # 21 x 26 bytes -> $FF1148 + 50 k ($1BB58)
SCEN_PERSON_COUNT = 531
PROVINCE_COUNT = 46
SCEN_PROVINCE_SIZE = 32
FACTION_COUNT = 21
FACTION_SIZE = 26
# 22 x 6 bytes [i * 6 + scenario] -> $FF111C ($1BBD4), meaning unknown
SCEN_EXTRA = 0x800E4
SCEN_EXTRA_COUNT = 22
# Province names: 26 bytes = 2 bytes, name (7), reading (8 half-width katakana), pad, 4 BE16 (words 0-1: map
# column + 1 and row of the province's cell, words 2-3 unknown)
PROVINCE_NAMES = 0x7EF74
PROVINCE_NAME_SIZE = 26
# Strategic map ($EC66 loads the tiles): MAP_W x MAP_H BE16 name-table words (palette 1, tiles 0x400+) at MAP;
# the 0x2A1 tiles at MAP_TILES go to VRAM tile 0x400. The 46 cells with tile MAP_PROVINCE_TILE are where the game
# puts the province markers (tile 0x3BC + province id). Palette: CRAM line 1 = MAP_PALETTE (16 colours).
MAP = 0xA2524
MAP_W, MAP_H = 30, 28
MAP_TILES = 0x9D104
MAP_TILE_COUNT = 0x2A1
MAP_TILE_BASE = 0x400
MAP_PALETTE = 0x8BA70
MAP_PROVINCE_TILE = 0x242A
# Battlefields ($47F20): LZ stream TACTICAL_PTRS[$FF9014] -> $FFCC04, 1342 bytes = 3 layers of TACTICAL_W
# columns (A 21 rows, B 20, C 20), byte-identical to the SFC version's data entries 47-114: 0-45 are the
# battlefields of province index 0-45, 46-67 the SFC's unexplained entries 93-114.
TACTICAL_PTRS = 0x8A7EC
TACTICAL_COUNT = 68
TACTICAL_SIZE = 1342
TACTICAL_W = 22
TACTICAL_LAYERS = ((0, 21), (462, 20), (902, 20))  # (offset, rows)
# Items: 13 x 18 bytes (5 bytes + name); owners [item * 6 + scenario] BE16 person -> $FF07AA ($1BC0C)
ITEMS = 0x80414
ITEM_COUNT = 13
ITEM_SIZE = 18
ITEM_OWNERS = 0x80378
NONE16 = 0xFFFF

# Faces ($F42C): 40x48 = 5x6 4bpp tiles, row-major, built in the buffer $FFB004.
#   FFFF random; bit 15 composite ($F1F2); else plain face n ($F3B0): LZ stream from one of 4 pointer tables
#   by (n - 1) // 100, 960 bytes; palette number FACE_PAL_NO[n - 1] (composite faces: 0).
# Palette ($F46A): 15 colours at FACE_PALETTES + 32 * palette number, to CRAM line 2 or 3 (by screen slot, not by
# palette number). Colour 15 is not loaded: it keeps the screen's own value, 0x6CE on line 3 / 0x6C4 on line 2 of
# the province panel; faces 77, 123, 172 and 227 use it (31 pixels). Exports draw it as FACE_COLOUR15.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
FACE_COUNT = 307
FACE_TABLES = (0xF7F1E, 0x10A23C, 0x11C7D6, 0x11DC5E)  # base for index n - 1 (each holds 100, the last 7)
FACE_PAL_NO = 0x8B7CC
FACE_PALETTES = 0x8BBB0
FACE_PAL_COLOURS = 15
FACE_COLOUR15 = 0x6CE
# Composite faces: type t = bit 14 * 8 + (face & 7) (0-12 used); 30 bytes per type at COMPOSITE_TYPES =
# 5 parts x (long pointer, first tile, tile count); part p variant v copies tile count tiles from
# pointer + 32 * tiles * v to the buffer from the first tile. Variants: parts 0-4 = bits 3-4, 5-6, 7-9, 10, 11-12.
COMPOSITE_TYPES = 0x8AA5E
COMPOSITE_TYPE_COUNT = 13
PART_VARIANTS = (4, 4, 6, 2, 4)  # stored variants of parts 0-4 (part 2 has 3 code bits but 6 stored)
# MAME's levels of the 3-bit MD colour values (its screenshots use them; the other MD exporters here do too)
LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)


def be16(raw: bytes, i: int) -> int:
    return raw[i] << 8 | raw[i + 1]


def be32(raw: bytes, i: int) -> int:
    return int.from_bytes(raw[i:i + 4], "big")


def decode_tile(raw: bytes) -> list[int]:
    """64 colour numbers of an MD 4bpp tile (row-major, high nibble first)."""
    return [raw[i // 2] >> (4 if i % 2 == 0 else 0) & 15 for i in range(64)]


def md_rgb(c: int) -> tuple[int, int, int]:
    """MD CRAM word (----BBB-GGG-RRR-) to RGB (MAME's levels)."""
    return tuple(LEVELS[c >> s & 7] for s in (1, 5, 9))


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = load_rom(path)

    def ptr(self, at: int) -> int:
        return be32(self.data, at)

    # --- text ---

    def text(self, raw: bytes) -> str:
        """Shift-JIS up to the first 00, with the game's gaiji."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            b = raw[i]
            if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
                code = b << 8 | raw[i + 1]
                out.append(GAIJI[code] if code in GAIJI else bytes(raw[i:i + 2]).decode("cp932"))
                i += 2
            else:
                out.append(bytes([b]).decode("cp932"))
                i += 1
        return "".join(out)

    def font_codes(self) -> list[int]:
        return [be16(self.data, FONT_CODES + 2 * i) for i in range(FONT_COUNT)]

    def glyph(self, i: int) -> list[list[int]]:
        """16x16 bitmap of glyph i."""
        base = FONT_GLYPHS + 32 * i
        g = [[0] * 16 for _ in range(16)]
        for t, (ox, oy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
            for y in range(8):
                b = self.data[base + 8 * t + y]
                for x in range(8):
                    g[oy + y][ox + x] = b >> (7 - x) & 1
        return g

    def scenario_titles(self) -> list[str]:
        return [self.text(self.data[self.ptr(SCENARIO_TITLES + 4 * i):][:40]) for i in range(SCENARIO_COUNT)]

    # --- static tables ---

    def persons(self) -> list[dict]:
        """+0 face BE16, +2 野心<<6 | 運<<4 | 冷静<<2 | 勇猛, +3 ?, +4 flags?, +5 陸指, +6 水指, +7 武力,
        +8 智力, +9 政治, +10 魅力, +11 相性, +12 義理, +13 血縁 (FF none), +14 生年 (AD),
        +15 name (Shift-JIS, 0-padded, 7 bytes), +22 reading (8 half-width katakana)."""
        out = []
        for pid in range(PERSON_COUNT):
            o = PERSONS + PERSON_SIZE * pid
            r = self.data[o:o + PERSON_SIZE]
            out.append({
                "id": pid, "offset": o, "raw": r, "face": be16(r, 0),
                "ambition": r[2] >> 6, "luck": r[2] >> 4 & 3, "calm": r[2] >> 2 & 3, "bravery": r[2] & 3,
                "unknown3": r[3], "flags4": r[4], "land": r[5], "water": r[6], "war": r[7], "int": r[8],
                "pol": r[9], "cha": r[10], "affinity": r[11], "duty": r[12], "kin": r[13], "born": r[14],
                "name": self.text(r[15:22]), "reading": r[22:30].rstrip(b"\0").decode("cp932"),
            })
        return out

    def provinces(self) -> list[dict]:
        """Province names; id 1-46 (scenario tables are 0-based: index id - 1)."""
        out = []
        for k in range(PROVINCE_COUNT):
            o = PROVINCE_NAMES + PROVINCE_NAME_SIZE * k
            r = self.data[o:o + PROVINCE_NAME_SIZE]
            out.append({"id": k + 1, "offset": o, "b0": r[0], "b1": r[1], "name": self.text(r[2:9]),
                        "reading": r[9:17].rstrip(b"\0").decode("cp932"),
                        "words": [be16(r, 18 + 2 * i) for i in range(4)]})
        return out

    def items(self) -> list[dict]:
        """+0 kind (0 書, 1 剣/矛, 2 馬, 3 青嚢書, 4 玉璽), +1, +2, +3 能力加算 (推測), +4, +5 name."""
        out = []
        for i in range(ITEM_COUNT):
            o = ITEMS + ITEM_SIZE * i
            r = self.data[o:o + ITEM_SIZE]
            out.append({"id": i, "kind": r[0], "b1": r[1], "b2": r[2], "bonus": r[3], "b4": r[4],
                        "name": self.text(r[5:18]),
                        "owners": [be16(self.data, ITEM_OWNERS + 12 * i + 2 * sc) for sc in range(SCENARIO_COUNT)]})
        return out

    # --- scenarios ---

    def scenario_header(self, sc: int) -> dict:
        """+0 BE16 start year - 1, +2 ?, +3 number of factions, +4..21 flag colour per faction, +22..32 ?, +33 pad."""
        r = self.data[SCENARIO_HEADER + HEADER_SIZE * sc:SCENARIO_HEADER + HEADER_SIZE * (sc + 1)]
        return {"raw": r, "year": be16(r, 0) + 1, "factions": r[3], "colours": list(r[4:22])}

    def scenario_persons(self, sc: int) -> list[dict]:
        """4 bytes per person: 兵士 / 100 (FF: none), rank (bit 7 flag, low 7 bits: 0 君主 1 軍師 2 将軍
        3 武官 4 文官 5-7 not in a faction; FF: not in play), 忠誠, province (0-based, FF none)."""
        base = self.ptr(SCEN_PERSON_PTRS + 4 * sc)
        out = []
        for pid in range(SCEN_PERSON_COUNT):
            r = self.data[base + 4 * pid:base + 4 * pid + 4]
            out.append({"id": pid, "raw": r, "soldiers": r[0] * 100, "rank_byte": r[1], "rank": r[1] & 0x7F,
                        "rank_flag": r[1] >> 7, "loyalty": r[2], "province": r[3]})
        return out

    def scenario_provinces(self, sc: int) -> list[dict]:
        """32 bytes per province (index 0-45): the SFC record with BE words and pad bytes at +1 and +31; unknown
        fields keep the SFC names (b9 = SFC +9 = MD +10 ...)."""
        base = self.ptr(SCEN_PROVINCE_PTRS + 4 * sc)
        out = []
        for k in range(PROVINCE_COUNT):
            r = self.data[base + SCEN_PROVINCE_SIZE * k:base + SCEN_PROVINCE_SIZE * (k + 1)]
            out.append({
                "id": k, "raw": r, "next": r[0], "w1": be16(r, 2), "population": be16(r, 4) * 10000,
                "gold": be16(r, 6) * 100, "food": be16(r, 8) * 100, "b9": r[10], "b10": r[11], "b11": r[12],
                "develop": r[13], "b13": r[14], "flood": r[15], "commerce": be16(r, 16), "tax": r[18],
                "loyalty": r[19], "w19": be16(r, 20), "w21": be16(r, 22), "w23": be16(r, 24),
                "b25": r[26], "b26": r[27], "b27": r[28], "training": r[29], "morale": r[30],
            })
        return out

    def scenario_factions(self, sc: int) -> list[dict]:
        """26 bytes per faction slot: +0 BE16 ruler (FFFF = empty slot), +2 capital province (0-based),
        +3 ?, +4..24 21 bytes (one per faction slot, 推測: relations), +25 pad."""
        base = self.ptr(SCEN_FACTION_PTRS + 4 * sc)
        out = []
        for k in range(FACTION_COUNT):
            r = self.data[base + FACTION_SIZE * k:base + FACTION_SIZE * (k + 1)]
            out.append({"id": k, "raw": r, "ruler": be16(r, 0), "capital": r[2], "b3": r[3], "rel": list(r[4:25])})
        return out

    def scenario_extra(self, sc: int) -> list[int]:
        return [self.data[SCEN_EXTRA + 6 * i + sc] for i in range(SCEN_EXTRA_COUNT)]

    def province_factions(self, sc: int) -> dict[int, int]:
        """Province index -> faction slot at the start of scenario sc (each faction's chain from its capital)."""
        provs = self.scenario_provinces(sc)
        out = {}
        for fa in self.scenario_factions(sc):
            k, seen = fa["capital"], 0
            while fa["ruler"] != NONE16 and k != 0xFF and seen < PROVINCE_COUNT:
                out[k] = fa["id"]
                k, seen = provs[k]["next"], seen + 1
        return out

    # --- map ---

    def map_words(self) -> list[list[int]]:
        return [[be16(self.data, MAP + 2 * (MAP_W * y + x)) for x in range(MAP_W)] for y in range(MAP_H)]

    def map_cells(self) -> list[tuple[int, int] | None]:
        """Map cell (column, row) of provinces 1-46 from the name table's words 0-1; None if they don't point at
        a province cell (南海: words 135, 262)."""
        words = self.map_words()
        out = []
        for p in self.provinces():
            x, y = p["words"][0] - 1, p["words"][1]
            out.append((x, y) if 0 <= x < MAP_W and 0 <= y < MAP_H and words[y][x] == MAP_PROVINCE_TILE else None)
        return out

    def map_tile(self, w: int) -> list[int]:
        """64 colour numbers of a name-table word's tile, flips applied."""
        px = decode_tile(self.data[MAP_TILES + 32 * ((w & 0x7FF) - MAP_TILE_BASE):][:32])
        return [px[(7 - i // 8 if w & 0x1000 else i // 8) * 8 + (7 - i % 8 if w & 0x800 else i % 8)]
                for i in range(64)]

    def map_rgb(self) -> list[tuple[int, int, int]]:
        """(MAP_W * 8) x (MAP_H * 8) pixels, row-major; province cells are the empty marker tile."""
        pal = [md_rgb(be16(self.data, MAP_PALETTE + 2 * i)) for i in range(16)]
        w = MAP_W * 8
        out = [(0, 0, 0)] * (w * MAP_H * 8)
        for y, row in enumerate(self.map_words()):
            for x, word in enumerate(row):
                for i, v in enumerate(self.map_tile(word)):
                    out[(y * 8 + i // 8) * w + x * 8 + i % 8] = pal[v]
        return out

    # --- battlefields ---

    def tactical_raw(self, k: int) -> bytes:
        return lz.decompress(self.data, self.ptr(TACTICAL_PTRS + 4 * k))[0][:TACTICAL_SIZE]

    def tactical_map(self, k: int) -> list[list[list[int]]]:
        """Battlefield k: [layer A, layer B, layer C], each a list of rows of TACTICAL_W."""
        d = self.tactical_raw(k)
        return [[list(d[o + TACTICAL_W * y:o + TACTICAL_W * (y + 1)]) for y in range(rows)] for o, rows in TACTICAL_LAYERS]

    # --- faces ---

    def face_stream(self, n: int) -> int:
        """File offset of plain face n's LZ stream (1-307)."""
        return self.ptr(FACE_TABLES[min((n - 1) // 100, 3)] + 4 * (n - 1))

    def face_palette_no(self, face: int) -> int:
        return 0 if face & 0x8000 else self.data[FACE_PAL_NO + face - 1]

    def face_palette(self, face: int) -> list[int]:
        """16 CRAM words; colour 15 is not loaded by the game (FACE_COLOUR15 here)."""
        return self.palette(self.face_palette_no(face))

    def palette(self, no: int) -> list[int]:
        at = FACE_PALETTES + 32 * no
        return [be16(self.data, at + 2 * i) for i in range(FACE_PAL_COLOURS)] + [FACE_COLOUR15]

    def composite_type(self, face: int) -> int:
        return (face >> 14 & 1) * 8 + (face & 7)

    def composite_variants(self, face: int) -> list[int]:
        return [face >> 3 & 3, face >> 5 & 3, face >> 7 & 7, face >> 10 & 1, face >> 11 & 3]

    def composite_parts(self, t: int) -> list[tuple[int, int, int]]:
        """(source, first tile, tile count) of parts 0-4 of type t."""
        r = self.data[COMPOSITE_TYPES + 30 * t:COMPOSITE_TYPES + 30 * (t + 1)]
        return [(be32(r, 6 * p), r[6 * p + 4], r[6 * p + 5]) for p in range(5)]

    def composite_part(self, t: int, p: int, v: int) -> list[tuple[int, bytes]]:
        """(tile number in the face, 32 bytes) of variant v of part p of type t."""
        src, first, n = self.composite_parts(t)[p]
        return [(first + i, self.data[src + 32 * (n * v + i):src + 32 * (n * v + i + 1)]) for i in range(n)]

    def face_tiles(self, face: int) -> bytes:
        """960 bytes: the 30 tiles of a face as the game puts them in VRAM."""
        if face == NONE16:
            raise ValueError("random face")
        if not face & 0x8000:
            return lz.decompress(self.data, self.face_stream(face))[0][:FACE_BYTES]
        out = bytearray(FACE_BYTES)
        for p, v in enumerate(self.composite_variants(face)):
            for cell, raw in self.composite_part(self.composite_type(face), p, v):
                out[32 * cell:32 * cell + 32] = raw
        return bytes(out)

    def face_pixels(self, face: int) -> list[int]:
        """40x48 colour numbers, row-major."""
        tiles = self.face_tiles(face)
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, face: int) -> list[tuple[int, int, int]]:
        pal = [md_rgb(c) for c in self.face_palette(face)]
        return [pal[v] for v in self.face_pixels(face)]
