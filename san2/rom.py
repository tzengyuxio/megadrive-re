"""MD 三國志II (KOEI, 1991) ROM decoding.

Offsets are file offsets of the 1 MB ROM (= 68000 addresses). The data tables are the SFC version's
(superfamicom-re san2) in big-endian form, some records widened; see san2/docs/ROM_FORMAT.md.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from triage import load_rom

DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Sangokushi II (Japan).zip")
KANJI_EXT = os.path.join(HERE, "data", "kanji_ext.json")

PERSON_COUNT = 352
NAME_TABLE = 0x4C8D4          # 352 x 16: kanji codes (7, BE16 each, 00-terminated) + reading (9, half-width kana)
NAME_SIZE = 16
PERSON_TABLE = 0x4BB14        # 352 x 10: 義理 人德 野望 相性, 親族 BE16, 生年, 00, 頭像 BE16
PERSON_SIZE = 10
ABILITY_TABLE = 0x4DED4       # 352 x 3: 才智 戰力 號召
SCENARIO_HEADER = 0x48DA2     # 6 x 20 bytes: year BE16 (game year - 1) + 18 unknown
SCENARIO_COUNT = 6
SCENARIO_YEARS = [189, 194, 201, 208, 215, 220]
LOYALTY = 0x4B2D4             # 352 x 6: loyalty per scenario (FF = absent; rulers and free generals 00)
PLACEMENT = 0x4F786           # 352 x 22: debut year, ?, province x6, id BE16, list link/flags BE16 x6
PLACEMENT_SIZE = 22
PROVINCE_COUNT = 41
PROVINCES = 0x48E7A           # 6 x 41 x 34: +16 gold, food, population BE16, +22 faction, +28 土 民 水 馬 信
PROVINCE_SIZE = 34
ADJACENCY = 0x5255A           # 41 x 6, 1-based, FF = none; slot d and 5-d are opposite hex sides
CURSOR_GRID = 0x4B112         # 8 x 9 grid of 0-based provinces for the map cursor (FF = none)
HEX_DIRS = [(1, 0), (1, -1), (0, -1), (0, 1), (-1, 1), (-1, 0)]  # axial step of each adjacency slot

# Battle fields: 41 x 78 = 13 x 12 hexes, 4 bits each (high nibble first), row-major (same bytes as FC/SFC)
BATTLE = 0x47A1A
BATTLE_COLS, BATTLE_ROWS = 13, 12
FORMATION = 0x4705A           # 13 x 12 nibble map, same as the FC/SFC one (not decoded)
TERRAIN = ["平地", "森", "林", "山", "河", "村", "城"]
TERRAIN_CELLS = 0x48AB6       # 7 x 4 plane entries BE16 (TL, TR, BL, BR) per terrain: tiles 0x1C0-0x1DB
BATTLE_GFX = 0xB0A8E          # tiles 0x1C0-0x1CF (平地..山)
RIVER_GFX = 0xB0C8E           # 河 tiles 0x1D0-0x1D3, 4 animation frames each: tile n frame j at +32 (4n + j)
RIVER_FRAME = 0
TOWN_GFX = 0xB0E8E            # tiles 0x1D4-0x1DB (村, 城)
BATTLE_PALETTES = [0x4E4F4, 0x4E574]  # CRAM lines 0 and 1 of the battle screen

# Big map: 28 x 18 tilemap (BE16 tile numbers) shown at plane cell (2, 3); tiles 0x1D0-0x380 are stored in order.
MAP_TILEMAP = 0x68900
MAP_TILES = 0x652E0           # tile 0x1D0
MAP_FIRST_TILE = 0x1D0
MAP_W, MAP_H = 28, 18
MAP_PALETTE = 0x4E3B4         # CRAM line 0 of the map screen
NUMBER_TILES = 0x68CF0        # tiles 0x1C0-0x1CF: province number labels drawn over the map

# Faces: 40x48 = 5x6 4bpp tiles, row-major, 960 bytes
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_TILES = 0x71D8E      # codes 1-208, in order
PORTRAIT_COUNT = 208
PORTRAIT_PALETTE = 0x515C6    # palette number (0-3) per portrait code - 1
FACE_PALETTES = 0x4E2F4       # 4 x 16 MD colours (0000BBB0GGG0RRR0)
COMPOSITE_TILES = 0xA928E     # 8 stored heads x 4 records (base, A, B, C) x 960 bytes
COMPOSITE_HEADS = 8
HEAD_SIZE = 4 * FACE_BYTES
COMPOSITE_PARTS = 0x45340     # 8 stored heads x 6 bytes: eyes/nose/mouth start column, then their widths
PART_ROWS = {"eyes": 2, "nose": 3, "mouth": 4}
# Composite face code: bit 15 set, bits 0-2 head, then a record number (0-3) per area, bits 13-14 palette.
COMPOSITE_SLOTS = [("top", "上", 3), ("bottom", "下", 5), ("eyes", "眼", 7), ("nose", "鼻", 9), ("mouth", "口", 11)]

# Kanji font: 16x16 1bpp, 32 bytes = 4 8x8 tiles (TL, TR, BL, BR), one byte per row, MSB left.
FONT = 0x55896
# MAME's output levels of the MD's 3-bit colour channels (read off its screenshots)
LEVELS = [0, 52, 87, 116, 144, 172, 206, 255]


def stored_head(head: int) -> int:
    """Composite heads 0/1 are stored in slots 2/3 and vice versa ($65D0)."""
    return head + 2 if head < 2 else head - 2 if head < 4 else head


def glyph_offset(code: int) -> int:
    """ROM offset of a 2-byte kanji code's glyph ($4560). 85F0-85FF stand for 8n00 (n = 2, 3, ...), whose
    low byte 00 cannot sit in a 00-terminated string; the address arithmetic is 16-bit, as in the game."""
    if code >= 0x85F0:
        idx = ((code << 8) + 0xC0C0) & 0xFFFF
    else:
        idx = (code - 0x8140) & 0xFFFF
    d = (idx << 5) & 0xFFFF
    return FONT + (d - 0x10000 if d & 0x8000 else d)


def kana(raw: bytes) -> str:
    """Half-width katakana (cp932), 00-terminated or field-filling."""
    return raw.split(b"\0")[0].decode("cp932")


def is_composite(code: int) -> bool:
    return bool(code & 0x8000)


def decode_tile(raw: bytes) -> list[int]:
    """One MD tile (32 bytes, 4 bits per pixel, left pixel in the high nibble) -> 64 colour numbers."""
    return [v for b in raw for v in (b >> 4, b & 15)]


def md_rgb(c: int) -> tuple[int, int, int]:
    """MD colour (0000BBB0GGG0RRR0) -> 8-bit RGB as MAME shows it."""
    return tuple(LEVELS[c >> s & 7] for s in (1, 5, 9))


def load_kanji() -> dict[int, str]:
    with open(KANJI_EXT, encoding="utf-8") as f:
        return {int(k, 16): v for k, v in json.load(f).items() if not k.startswith("_")}


def be16(b: bytes, o: int) -> int:
    return b[o] << 8 | b[o + 1]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom(path)

    def scenarios(self) -> list[dict]:
        out = []
        for s in range(SCENARIO_COUNT):
            o = SCENARIO_HEADER + 20 * s
            out.append({"year": be16(self.data, o) + 1, "raw": self.data[o + 2:o + 20]})
        return out

    def persons(self) -> list[dict]:
        out, d = [], self.data
        for i in range(PERSON_COUNT):
            n = d[NAME_TABLE + NAME_SIZE * i:NAME_TABLE + NAME_SIZE * (i + 1)]
            codes = [be16(n, k) for k in range(0, 6, 2) if n[k]]
            o = PERSON_TABLE + PERSON_SIZE * i
            p = d[o:o + PERSON_SIZE]
            a = d[ABILITY_TABLE + 3 * i:ABILITY_TABLE + 3 * (i + 1)]
            out.append({
                "id": i, "kanji_codes": codes, "reading": kana(n[7:16]),
                "int": a[0], "war": a[1], "charm": a[2],
                "duty": p[0], "virtue": p[1], "ambition": p[2], "compat": p[3],
                "kin": be16(p, 4), "born": p[6], "face": be16(p, 8), "offset": o,
            })
        return out

    def glyph(self, code: int) -> list[list[int]]:
        """16x16 bitmap (rows of 0/1) of a 2-byte kanji code."""
        g = self.data[glyph_offset(code):][:32]
        return [[g[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    # ------------------------------------------------------------------ scenarios
    def placement(self, n: int, sc: int) -> dict | None:
        """Where person n starts in scenario sc (None = not in the scenario)."""
        pl, d = PLACEMENT + PLACEMENT_SIZE * n, self.data
        assert be16(d, pl + 8) == n
        prov, loyalty, flags = d[pl + 2 + sc], d[LOYALTY + 6 * n + sc], d[pl + 10 + 2 * sc]
        if prov == 0xFF:
            return None
        appears = loyalty != 0xFF or d[pl] == SCENARIO_YEARS[sc] - 1  # the game starts in December of the year before
        status = "未登場" if not appears else "君主" if flags & 0x80 else "在野" if flags & 0x20 else "武將"
        soldiers = 0 if not appears or flags & 0x20 else 100 if flags & 0x80 else 50 if flags & 0x10 else 10
        return {"province": prov + 1, "status": status, "soldiers": soldiers,
                "loyalty": loyalty if status == "武將" and loyalty != 0xFF else None}

    def debut(self, n: int) -> int | None:
        v = self.data[PLACEMENT + PLACEMENT_SIZE * n]
        return None if v == 0xFF else v

    def province(self, sc: int, i: int) -> dict:
        o = PROVINCES + PROVINCE_SIZE * (PROVINCE_COUNT * sc + i)
        r = self.data[o:o + PROVINCE_SIZE]
        return {"province": i + 1, "gold": be16(r, 16), "food": be16(r, 18), "population": be16(r, 20),
                "faction": None if r[22] == 0xFF else r[22],
                "land": r[28], "loyalty": r[29], "flood": r[30], "horses": r[31], "trust": r[32]}

    def faction_rulers(self, sc: int) -> dict[int, int]:
        """Faction index -> ruler's person id: the ruler (flag 0x80) standing in a province of that faction."""
        out = {}
        for n in range(PERSON_COUNT):
            p = self.placement(n, sc)
            if p and p["status"] == "君主":
                out[self.province(sc, p["province"] - 1)["faction"]] = n
        return out

    def adjacency(self) -> list[list[int | None]]:
        """Per province, the neighbour (1-based) on each of the 6 hex sides (None = no neighbour)."""
        return [[None if v == 0xFF else v for v in self.data[ADJACENCY + 6 * i:ADJACENCY + 6 * i + 6]]
                for i in range(PROVINCE_COUNT)]

    def hex_layout(self) -> dict[int, tuple[int, int]]:
        """Axial hex coordinates of every province, following the sides of the adjacency table."""
        adj, pos, todo = self.adjacency(), {1: (0, 0)}, [1]
        while todo:
            i = todo.pop()
            for d, j in enumerate(adj[i - 1]):
                if j is None:
                    continue
                q = (pos[i][0] + HEX_DIRS[d][0], pos[i][1] + HEX_DIRS[d][1])
                if j in pos:
                    assert pos[j] == q, (i, j)
                else:
                    pos[j] = q
                    todo.append(j)
        assert len(pos) == PROVINCE_COUNT and len(set(pos.values())) == PROVINCE_COUNT
        return pos

    def battle_terrain(self, i: int) -> list[list[int]]:
        """13 x 12 terrain ids (rows of columns 0-12) of province i's battle field (0-based)."""
        d = self.data[BATTLE + 78 * i:BATTLE + 78 * i + 78]
        nib = [v for b in d for v in (b >> 4, b & 15)]
        return [nib[r * BATTLE_COLS:(r + 1) * BATTLE_COLS] for r in range(BATTLE_ROWS)]

    def terrain_cells(self) -> list[list[int]]:
        """Per terrain, its 4 plane entries (TL, TR, BL, BR)."""
        return [[be16(self.data, TERRAIN_CELLS + 8 * t + 2 * k) for k in range(4)] for t in range(len(TERRAIN))]

    def battle_tile_offset(self, entry: int, frame: int = RIVER_FRAME) -> int:
        n = entry & 0x7FF
        if n >= 0x1D4:
            return TOWN_GFX + 32 * (n - 0x1D4)
        if n >= 0x1D0:
            return RIVER_GFX + 32 * (4 * (n - 0x1D0) + frame)
        return BATTLE_GFX + 32 * (n - 0x1C0)

    def battle_pixels(self, i: int) -> tuple[int, int, list[tuple[int, int, int]]]:
        """Province i's battle field as the game draws it (26 x 25 tiles, odd columns half a hex lower)."""
        pal, cells = [c for o in BATTLE_PALETTES for c in self.palette(o)], self.terrain_cells()
        w, h = 16 * BATTLE_COLS, 8 * (2 * BATTLE_ROWS + 1)
        out = [pal[0]] * (w * h)
        for r, row in enumerate(self.battle_terrain(i)):
            for c, t in enumerate(row):
                for k, e in enumerate(cells[t]):
                    x0, y0 = 16 * c + 8 * (k % 2), 16 * r + 8 * (c % 2) + 8 * (k // 2)
                    o = self.battle_tile_offset(e)
                    for j, v in enumerate(decode_tile(self.data[o:o + 32])):
                        out[(y0 + j // 8) * w + x0 + j % 8] = pal[(e >> 13 & 3) * 16 + v]
        return w, h, out

    def palette(self, offset: int, count: int = 1) -> list[tuple[int, int, int]]:
        """count x 16 MD colours at offset -> RGB."""
        return [md_rgb(be16(self.data, offset + 2 * i)) for i in range(16 * count)]

    # ------------------------------------------------------------------ big map
    def map_tilemap(self) -> list[int]:
        """28 x 18 tile numbers of the big map, row-major."""
        return [be16(self.data, MAP_TILEMAP + 2 * i) for i in range(MAP_W * MAP_H)]

    def map_tile(self, n: int) -> list[int]:
        o = MAP_TILES + 32 * (n - MAP_FIRST_TILE)
        return decode_tile(self.data[o:o + 32])

    def map_pixels(self) -> list[tuple[int, int, int]]:
        """The big map (224 x 144) without province labels or faction colours, RGB row-major."""
        pal, w = self.palette(MAP_PALETTE), MAP_W * 8
        out = [pal[0]] * (w * MAP_H * 8)
        for i, n in enumerate(self.map_tilemap()):
            for k, v in enumerate(self.map_tile(n & 0x7FF)):
                out[(i // MAP_W * 8 + k // 8) * w + i % MAP_W * 8 + k % 8] = pal[v]
        return out

    # ------------------------------------------------------------------ faces
    def face_palettes(self) -> list[list[int]]:
        """The 4 face palettes as MD colour words (16 each)."""
        return [[be16(self.data, FACE_PALETTES + 32 * p + 2 * i) for i in range(16)] for p in range(4)]

    def portrait_offset(self, code: int) -> int:
        return PORTRAIT_TILES + (code - 1) * FACE_BYTES

    def composite_areas(self, head: int) -> dict[str, set[int]]:
        """Cell numbers (0-29) of each slot for a head (code bits 0-2)."""
        s = stored_head(head)
        p = self.data[COMPOSITE_PARTS + 6 * s:COMPOSITE_PARTS + 6 * s + 6]
        areas = {}
        for k, name in enumerate(("eyes", "nose", "mouth")):
            row = PART_ROWS[name]
            areas[name] = {row * FACE_W + p[k] + i for i in range(p[3 + k])}
        parts = areas["eyes"] | areas["nose"] | areas["mouth"]
        boundary = 10 if s == 3 else 15  # cells taken from the "top" record ($668C)
        areas["top"] = {c for c in range(boundary) if c not in parts}
        areas["bottom"] = {c for c in range(boundary, FACE_W * FACE_H) if c not in parts}
        return areas

    def composite_record(self, head: int, record: int) -> int:
        return COMPOSITE_TILES + stored_head(head) * HEAD_SIZE + record * FACE_BYTES

    def face_cells(self, code: int) -> list[int]:
        """ROM offset of each of the 30 tiles of a face."""
        if not is_composite(code):
            base = self.portrait_offset(code)
            return [base + 32 * c for c in range(30)]
        head, cells = code & 7, [0] * 30
        for sid, _, shift in COMPOSITE_SLOTS:
            record = self.composite_record(head, code >> shift & 3)
            for c in self.composite_areas(head)[sid]:
                cells[c] = record + 32 * c
        return cells

    def face_palette_number(self, code: int) -> int:
        return code >> 13 & 3 if is_composite(code) else self.data[PORTRAIT_PALETTE + code - 1]

    def face_pixels(self, code: int) -> bytes:
        """40x48 colour numbers (0-15) of a face, row-major."""
        tiles = [decode_tile(self.data[o:o + 32]) for o in self.face_cells(code)]
        return bytes(tiles[(y // 8) * FACE_W + x // 8][(y % 8) * 8 + x % 8]
                     for y in range(FACE_H * 8) for x in range(FACE_W * 8))
