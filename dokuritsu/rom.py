"""MD Liberty or Death (KOEI, 1994, USA only) ROM decoding.

Offsets are ROM offsets (= 68000 addresses); RAM addresses are offsets in $FF0000-$FFFFFF. See docs/ROM_FORMAT.md.
The game is the SFC 独立戦争 (~/works/superfamicom-re/dokuritsu) rewritten in 68000 C and translated: the same
tables in the same order (250 persons sorted by surname, 53 locations, 15 states, the 1775 scenario), records
widened, big-endian, 4-byte pointers, ASCII text. Faces are KOEI LZ streams (tools/koei_lz.py; the MD decoder has
no lookup tables, so the SFC table block is appended to the ROM image for decoding).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz
from triage import load_rom

DEFAULT_ROM = os.path.join(REPO, "roms", "Liberty or Death (USA).zip")

# ---------------------------------------------------------------- static tables
# Persons: 250 x 36 bytes, the SFC order. +0 given name (12, NUL padded), +12 surname (15), +27..+30 stats,
# +31 / +32 = SFC +29 / +30 (unknown), +33 0, +34 face code (BE16). The SFC initial letter is gone (full given names).
PERSONS, PERSON_SIZE, PERSON_COUNT = 0x5CAF2, 36, 250
STATS = [("体力", "Health"), ("統率力", "Leadership"), ("戦術力", "Tactics"), ("指導力", "Discipline")]
# Locations: 53 x 32 bytes. +0 / +1 = SFC +0 / +1 (unknown), +2 name (20), +22 neighbours (8, FF padded),
# +30 = SFC +24 (bits 0-1 region, 2-5 state, 6 port (guess)), +31 0.
LOCATIONS, LOCATION_SIZE, LOCATION_COUNT = 0x5BFF6, 32, 53
REGIONS = ["North", "Central", "South"]
# States: 15 long pointers each, abbreviation and full name.
STATE_ABBR, STATE_NAMES, STATE_COUNT = 0x61D10, 0x61D4C, 15

# Event persons (Continental Congress / British side, no person record): 44 x 24 bytes, +0 given name (10),
# +10 surname (14). Record k is drawn with portrait EVENT_FIRST_PORTRAIT + k (e.g. $231C2, $1B59A; John Hancock,
# record 19 = portrait 144, seen on the Congress screen). Records 20, 21, 42, 43 are blank (the quartermaster and
# commissary faces, by the PC-98 order). Portraits 169-173 have no record.
EVENT_PERSONS, EVENT_SIZE, EVENT_COUNT, EVENT_FIRST_PORTRAIT = 0x5C696, 24, 44, 0x7D

# ---------------------------------------------------------------- the 1775 scenario
# "Start New Game" ($97EC) copies SCENARIO_ROM to RAM $FF000A..$FF16BA (memcpy $5F1E). Same blocks as the SFC
# WRAM $2009..$3DB5, in the same order, with 2-byte pointers widened to 4 and LE words to BE.
SCENARIO_ROM, SCENARIO_RAM, SCENARIO_SIZE = 0x5A946, 0x000A, 0x16B1
UNKNOWN_A = (0x000A, 0x50)            # SFC $2009 (0x47 bytes) + padding, unknown
UNKNOWN_B, UNKNOWN_B_SIZE, UNKNOWN_B_COUNT = 0x005A, 6, 13      # SFC $2054 (13 x 5), unknown
LOC_STATES, LOC_STATE_SIZE = 0x00A8, 18     # SFC $2095 (53 x 14)
UNKNOWN_C = (0x0462, 0x58)            # SFC $237B: 2 x (20 words of 70 + 4 bytes)
SIDES, SIDE_SIZE = 0x04BA, 54         # SFC $23A7 (2 x 49)
PERSON_STATES, PERSON_STATE_SIZE = 0x0526, 18   # SFC $2409 (250 x 14)
NOT_PLACED = 0x35                     # person state +4: waiting with the side, not at a location
SIDE_NAMES = ["America", "Britain"]

# ---------------------------------------------------------------- faces
# $EE6A / $EF76 (face code, slot): bit 15 clear = portrait n, a KOEI LZ stream of 960 bytes (5 x 6 4bpp tiles, row
# by row) from one of three long-pointer tables (n < 0x50, < 0x81, else; each indexed by n itself); bit 15 set =
# composite ($EC82). One palette, FACE_PALETTE (16 words), loaded to CRAM line 1.
PORTRAIT_TABLES = [(0x00, 0x10676A), (0x50, 0x10F498), (0x81, 0x117252)]
PORTRAIT_COUNT = 174
FACE_PALETTE = 0x6200C
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
# Composite: code bits 10-11 = type t (0-3); TYPES + 30 t holds 5 part entries of 6 bytes (long pointer to the
# uncompressed tiles, first tile in the face, tile count). Variant v of a part = tiles from ptr + 32 * count * v.
# The game copies part 4, 0, 1, 2, 3 in that order into the face buffer, the variant taken from code bits
# PART_BITS[p]. Type 0, part 0: only count - 5 tiles from the first, then the variant's tiles 20 and 24 to face
# tiles 20 and 24.
TYPES, TYPE_COUNT, PART_COUNT = 0x628B0, 4, 5
PART_ORDER = [4, 0, 1, 2, 3]
PART_BITS = [8, 4, 2, 0, 6]           # part p uses (code >> PART_BITS[p]) & 3
# ---------------------------------------------------------------- the strategy map
# 3 regions (North, Central, South), each 672 uncompressed 4bpp tiles from the long-pointer table MAP_TILES
# (indexed by region; a 4th pointer is MAP_TILEMAP). $DE70 copies them to VRAM tile 0x1C0 ($4D06) and the 672-word
# tilemap MAP_TILEMAP (0x21C0 + i: palette 1, 28 x 24 tiles, row by row, the same for every region) to RAM $FF62C0;
# plane at VRAM $F000 (32 cells wide), from cell (2, 2). Palette MAP_PALETTE (CRAM line 1); colours 9-11 (water)
# cycle through the next two palettes.
MAP_TILES, MAP_TILEMAP, MAP_PALETTE = 0xC943C, 0xC9448, 0x632EE
MAP_W, MAP_H, MAP_FIRST_TILE = 28, 24, 0x1C0
# ---------------------------------------------------------------- battle (HEX) maps
# BATTLE_LAYERS holds 2 long pointers to KOEI LZ streams, layer A (16-byte "LIBERTY_HEX_MAP" header + 53 maps) and
# layer B (53 maps); $A69E / $A6FE decode one into $FF7FB0 and copy map (location) n. Each map is 14 x 12 hexes,
# one BE word per hex, row by row. A: bits 0-3 terrain 0-10, 4-7 and 8-15 unknown; B: 4 nibbles = the tiles of a
# river / ford / sea hex (0x8888 plain, 0xFFFF none). The same data as the SFC entries 1 / 2, as BE words.
BATTLE_LAYERS = 0x612DE
BATTLE_HEADER, BATTLE_W, BATTLE_H = 16, 14, 12
BATTLE_MAP_BYTES = 2 * BATTLE_W * BATTLE_H
TERRAIN_LOOKS = ["草地", "森林", "丘陵", "山", "河川", "淺灘", "（未使用）", "海・湖", "城鎮", "要塞", "柵欄陣地"]  # SFC
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def be16(raw, o: int) -> int:
    return raw[o] << 8 | raw[o + 1]


def be32(raw, o: int) -> int:
    return be16(raw, o) << 16 | be16(raw, o + 2)


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


def cstr(raw: bytes) -> str:
    return raw.split(b"\0")[0].decode("latin-1")


def packed_pixels(raw: bytes, w: int, h: int) -> list[int]:
    """w x h packed 4bpp tiles, row by row -> (8 w) x (8 h) colour indices."""
    out = [0] * (64 * w * h)
    for t in range(w * h):
        for i in range(64):
            b = raw[32 * t + i // 2]
            out[((t // w) * 8 + i // 8) * 8 * w + (t % w) * 8 + i % 8] = b >> 4 if i % 2 == 0 else b & 15
    return out


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom(path)
        self._lz = self.data + koei_lz.BLOCK
        self._portraits: dict[int, bytes] = {}

    def u16(self, o: int) -> int:
        return be16(self.data, o)

    def u32(self, o: int) -> int:
        return be32(self.data, o)

    def string(self, addr: int) -> str:
        return cstr(self.data[addr:addr + 64])

    # ------------------------------------------------------------ static tables
    def persons(self) -> list[dict]:
        out = []
        for i in range(PERSON_COUNT):
            o = PERSONS + PERSON_SIZE * i
            r = self.data[o:o + PERSON_SIZE]
            given, surname = cstr(r[0:12]), cstr(r[12:27])
            out.append({"id": i, "offset": o, "given": given, "surname": surname,
                        "name": f"{given} {surname}".strip(), **{en: r[27 + k] for k, (_, en) in enumerate(STATS)},
                        "kind": r[31] & 3, "unk31": r[31] >> 2, "unk32": r[32], "face": be16(r, 34)})
        return out

    def event_persons(self) -> list[dict]:
        out = []
        for k in range(EVENT_COUNT):
            r = self.data[EVENT_PERSONS + EVENT_SIZE * k:][:EVENT_SIZE]
            given, surname = cstr(r[:10]).strip(), cstr(r[10:]).strip()
            out.append({"id": k, "portrait": EVENT_FIRST_PORTRAIT + k, "name": f"{given} {surname}".strip()})
        return out

    def states(self) -> list[dict]:
        return [{"id": i, "abbr": self.string(self.u32(STATE_ABBR + 4 * i)),
                 "name": self.string(self.u32(STATE_NAMES + 4 * i))} for i in range(STATE_COUNT)]

    def locations(self) -> list[dict]:
        out = []
        for i in range(LOCATION_COUNT):
            o = LOCATIONS + LOCATION_SIZE * i
            r = self.data[o:o + LOCATION_SIZE]
            out.append({"id": i, "offset": o, "name": cstr(r[2:22]), "neighbours": [x for x in r[22:30] if x != 0xFF],
                        "region": r[30] & 3, "state": r[30] >> 2 & 15, "port": r[30] >> 6 & 1,
                        "unk0": r[0], "flags1": r[1]})
        return out

    # ------------------------------------------------------------ the 1775 scenario
    def scenario_image(self) -> bytes:
        """RAM $FF000A..$FF16BA right after "Start New Game"."""
        return self.data[SCENARIO_ROM:SCENARIO_ROM + SCENARIO_SIZE]

    def _ram(self, addr: int, n: int) -> bytes:
        o = SCENARIO_ROM + addr - SCENARIO_RAM
        return self.data[o:o + n]

    @staticmethod
    def person_of(ptr: int) -> int:
        """RAM pointer to a person state -> person id."""
        return ((ptr & 0xFFFF) - PERSON_STATES) // PERSON_STATE_SIZE

    def person_states(self) -> list[dict]:
        out = []
        for i in range(PERSON_COUNT):
            r = self._ram(PERSON_STATES + PERSON_STATE_SIZE * i, PERSON_STATE_SIZE)
            out.append({"id": i, "next": be32(r, 0), "location": r[4], "health": r[5], "reputation": r[6],
                        "loyalty": r[7], "faction": r[8] >> 4, "unk8": r[8] & 15, "rank": r[9] & 3,
                        "flags9": r[9] & 0xFC, "unk10": r[10:18].hex(), "raw": r.hex(" ")})
        return out

    def person_list(self, head: int, states: list[dict] | None = None) -> list[int]:
        """Person ids along a list starting at RAM pointer head (0 ends it)."""
        states = states or self.person_states()
        out = []
        while head and len(out) < PERSON_COUNT:
            i = self.person_of(head)
            out.append(i)
            head = states[i]["next"]
        return out

    def location_states(self) -> list[dict]:
        out = []
        for i in range(LOCATION_COUNT):
            r = self._ram(LOC_STATES + LOC_STATE_SIZE * i, LOC_STATE_SIZE)
            out.append({"id": i, "head": be32(r, 0), "head2": be32(r, 4), "owner": r[8], "support": r[9],
                        "food": be16(r, 10), "weapons": be16(r, 12), "ammo": be16(r, 14), "unk16": r[16],
                        "raw": r.hex(" ")})
        return out

    def sides(self) -> list[dict]:
        out = []
        for i, name in enumerate(SIDE_NAMES):
            r = self._ram(SIDES + SIDE_SIZE * i, SIDE_SIZE)
            out.append({"id": i, "name": name, "commander": be32(r, 0), "reserve": be32(r, 4), "unk8": be16(r, 8),
                        "funds": be16(r, 10)})
        return out

    # ------------------------------------------------------------ faces
    def face_palette(self) -> list[int]:
        return [self.u16(FACE_PALETTE + 2 * k) for k in range(16)]

    def portrait_raw(self, n: int) -> bytes:
        if n not in self._portraits:
            table = next(t for lo, t in reversed(PORTRAIT_TABLES) if n >= lo)
            self._portraits[n] = koei_lz.decompress(self._lz, self.u32(table + 4 * n), len(self.data))[0][:FACE_BYTES]
        return self._portraits[n]

    def part(self, t: int, p: int) -> tuple[int, int, int]:
        """(tile pointer, first face tile, tile count) of part p of type t."""
        o = TYPES + 30 * t + 6 * p
        return self.u32(o), self.data[o + 4], self.data[o + 5]

    def part_variant(self, t: int, p: int, v: int) -> bytes:
        ptr, _, count = self.part(t, p)
        return self.data[ptr + 32 * count * v:][:32 * count]

    def composite_raw(self, code: int) -> bytes:
        """The face buffer $FF5D50 as $EC82 fills it."""
        t = code >> 10 & 3
        buf = bytearray(FACE_BYTES)
        for p in PART_ORDER:
            ptr, first, count = self.part(t, p)
            src = ptr + 32 * count * (code >> PART_BITS[p] & 3)
            n = 32 * count - (0xA0 if (t, p) == (0, 0) else 0)
            buf[32 * first:32 * first + n] = self.data[src:src + n]
            if (t, p) == (0, 0):
                for k in (0x280, 0x300):
                    buf[k:k + 32] = self.data[src + k:src + k + 32]
        return bytes(buf)

    def face_raw(self, code: int) -> bytes:
        return self.composite_raw(code) if code & 0x8000 else self.portrait_raw(code)

    def face_pixels(self, code: int) -> list[int]:
        return packed_pixels(self.face_raw(code), FACE_W, FACE_H)

    def face_rgb(self, code: int) -> list[tuple[int, int, int]]:
        pal = [md_rgb(c) for c in self.face_palette()]
        return [pal[c] for c in self.face_pixels(code)]

    # ------------------------------------------------------------ the strategy map
    def map_raw(self, region: int) -> bytes:
        ptr = self.u32(MAP_TILES + 4 * region)
        return self.data[ptr:ptr + 32 * MAP_W * MAP_H]

    def map_tilemap(self) -> list[int]:
        ptr = self.u32(MAP_TILEMAP)
        return [self.u16(ptr + 2 * i) for i in range(MAP_W * MAP_H)]

    def map_palette(self) -> list[int]:
        return [self.u16(MAP_PALETTE + 2 * k) for k in range(16)]

    def map_pixels(self, region: int) -> list[int]:
        """224 x 192 colour indices, the tiles placed by the tilemap (before the owner colouring)."""
        raw, tm = self.map_raw(region), self.map_tilemap()
        tiles = b"".join(raw[32 * ((e & 0x7FF) - MAP_FIRST_TILE):][:32] for e in tm)
        return packed_pixels(tiles, MAP_W, MAP_H)

    def map_rgb(self, region: int) -> list[tuple[int, int, int]]:
        pal = [md_rgb(c) for c in self.map_palette()]
        return [pal[c] for c in self.map_pixels(region)]

    # ------------------------------------------------------------ battle (HEX) maps
    def battle_layer(self, k: int) -> bytes:
        """Layer k (0 = A, 1 = B) as decoded into $FF7FB0."""
        return koei_lz.decompress(self._lz, self.u32(BATTLE_LAYERS + 4 * k), len(self.data))[0]

    def battle_map(self, m: int) -> list[dict]:
        a = self.battle_layer(0)[BATTLE_HEADER + BATTLE_MAP_BYTES * m:][:BATTLE_MAP_BYTES]
        b = self.battle_layer(1)[BATTLE_MAP_BYTES * m:][:BATTLE_MAP_BYTES]
        return [{"x": i % BATTLE_W, "y": i // BATTLE_W, "terrain": a[2 * i + 1] & 15, "flags": a[2 * i + 1] >> 4,
                 "byte1": a[2 * i], "overlay": be16(b, 2 * i)} for i in range(BATTLE_W * BATTLE_H)]
