"""MD 大航海時代II (KOEI, 1994) ROM decoding.

The data are those of the SFC version (superfamicom-re/daikoukai2) rebuilt as 68000 C structs: big-endian, 16-bit
fields word aligned, names moved out of the records and replaced by 32-bit ROM pointers. Text is JIS X0201
half-width kana (hiragana by default, ESC K / ESC H switch katakana on / off) mixed with Shift-JIS kanji. The faces
are the SFC drawings recoloured for one MD palette; portraits are compressed with KOEI's LZ (tools/koei_lz.py).
See docs/ROM_FORMAT.md.
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Daikoukai Jidai II (Japan).zip")

# ---------------------------------------------------------------- initial game state
# ROM INIT is copied to RAM $FF0000 ($136FC -> memcpy $7240) before the title screen; every table with a RAM address
# below lives in it (RAM = ROM - INIT + 0xFF0000).
INIT, INIT_RAM, INIT_SIZE = 0xD2516, 0xFF0000, 0x6E4C

# Persons 0-119 (RAM $FF0680): 32 bytes. 0-5 the playable heroes, 6-68 mates, 69-78 story characters, 79-119 rivals
# (order and contents as in the SFC version)
PERSONS, PERSON_COUNT, PERSON_SIZE = 0xD2B96, 120, 32
STATS = ["統率力", "航海術", "知識", "直感", "勇気", "剣技", "魅力"]   # +10..+16, names as in STAT_NAMES
HEROES = 6
# VIPs 0-19 (RAM $FF1580): name pointer, kind, 0, 0, face, ?, port
VIPS, VIP_COUNT, VIP_SIZE = 0xD3A96, 20, 10
# Women 0-29 (RAM $FF1648): name pointer, age?, port?, 0, FF, FF, ?
WOMEN, WOMAN_COUNT, WOMAN_SIZE = 0xD3B5E, 30, 10
# Ship types 0-24 (RAM $FF46EE): name pointer, number, flags?, ?, pad, BE16, BE16
SHIP_TYPES, SHIP_TYPE_COUNT, SHIP_TYPE_SIZE = 0xD6C04, 25, 12
# Ship specs 0-24 (ROM only): 12 bytes = 6 bytes, BE16, 2 bytes, BE16 (the SFC's LE16 fields at +6 / +10)
SHIP_SPECS, SHIP_SPEC_SIZE = 0xDA2B6, 12
# Ports 0-129 (RAM $FF481A): x, y (BE16, map cells), name pointer, flags (low nibble = country 0-5, 6 = none), pad;
# 0-99 trade ports (state below), 100-129 supply ports
PORTS, PORT_COUNT, PORT_SIZE = 0xD6D30, 130, 10
TRADE_PORTS = 100
# Port state 0-99 (RAM $FF4D2C): 38 bytes (the SFC's 37 with a pad byte after +0; 16-bit words big-endian, the 32-bit
# economy / industry low word first)
PORT_STATE, PORT_STATE_SIZE = 0xD7242, 38
# Items 0-99 (RAM $FF5F3E): name pointer, icon?, 0, price (BE16), power?, category (index in ITEM_CATEGORIES)
ITEMS, ITEM_COUNT, ITEM_SIZE = 0xD8454, 100, 10

# Tables of BE32 string pointers: (address, count)
STRING_TABLES = {
    "ranks": (0xD9478, 7),                  # "", 提督 ... 航海士
    "countries": (0xD9494, 7),              # ポルトガル ... オランダ, 海賊
    "skills": (0xD94B0, 5),                 # 測量 地図 砲術 会計 交渉
    "stat_names": (0xD94C4, 7),             # 統率力 ... 魅力
    "ship_slots": (0xD94E0, 10),            # 旗艦, 1号艦 ... 9号艦
    "woods": (0xD9508, 6),
    "figureheads": (0xD9520, 11),           # "", 海獣 ... 女神
    "discovery_categories": (0xD954C, 8),
    "item_categories": (0xD956C, 14),       # 剣 刺突剣 ... 秘宝
    "liquors": (0xD95A4, 14),
    "goods": (0xD95EA, 46),                 # (not word aligned)
    "name_pool": (0xD9FB6, 192),            # first / last names for new characters
    "discovery_texts": (0x97F48, 100),
    "discovery_names": (0x980D8, 100),
    "item_texts": (0x98330, 100),
}

# ---------------------------------------------------------------- faces (5 x 6 tiles, 4bpp packed, 960 bytes)
FACE_W, FACE_H = 5, 6
FACE_BYTES = FACE_W * FACE_H * 32
# Face code (person +8, VIP +6): bit 15 set = composite face ($59B4), else portrait number ($5A30)
PORTRAITS, PORTRAIT_COUNT = 0x1794BE, 134   # BE32 pointers to LZ streams ($5A30 -> $3C5E)
SFC_PORTRAITS = 128                         # 0-127 = the SFC portraits; 128-133 = heroes 0-5 for the hero select
FACE_PALETTE = 0x944D6                      # 16 words, loaded into CRAM line 3 ($B3D0, $B976)
GREY_PALETTE = 0x944F6                      # hero select: the heroes not chosen (CRAM line 2)
# Composite face ($5874): pack t = bits 12-14. Per pack 0xA0 bytes of BE32 pointers to uncompressed tiles
# (+0x00 upper by bits 9-11, +0x20 B by 6-8, +0x40 A1 by 3-5, +0x60 A2 by 3-5, +0x80 lower by 0-2) and 0x14 bytes of
# (first tile, count) BE16 in the order upper, B, A1, A2, lower. Copy order: lower, upper, B, A1, A2.
COMPOSITE_ADDR, COMPOSITE_TILES, COMPOSITE_PACKS = 0x8EFEA, 0x8F44A, 7
COMPOSITE_PARTS = [("lower", 0x80, 0x10, 0), ("upper", 0x00, 0x00, 9), ("b", 0x20, 0x04, 6),
                   ("a1", 0x40, 0x08, 3), ("a2", 0x60, 0x0C, 3)]   # (part, address offset, tile offset, code shift)

# ---------------------------------------------------------------- world map
# 90 x 45 blocks of 12 x 12 metatiles (2 x 2 cells) = 2160 x 1080 cells. Block b ($3C3E2): LZ stream at the BE32 in
# the row table MAP_ROWS[b / 90] + 4 (b % 90), decoded to $FFD210 (144 bytes). $3C470 expands it into 24 x 24 cells:
# metatile v >= 0x10 = 4 cell values at MAP_META + 4 v (TL TR BL BR), v < 0x10 = bits 8 4 2 1 (TL TR BL BR) set ->
# 0x80 (land) else 0 (sea). Block data and metatiles are those of the SFC version.
MAP_BLOCKS_W, MAP_BLOCKS_H, MAP_BLOCK = 90, 45, 12
MAP_W, MAP_H = MAP_BLOCKS_W * 2 * MAP_BLOCK, MAP_BLOCKS_H * 2 * MAP_BLOCK
MAP_ROWS = 0x93B98
MAP_META = 0xC1DEE
MAP_BANDS = 0x8FA00                         # BE16 per block row ($122C4: band = v + 1 if v <= 4 else 9 - v)
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def be16(b: bytes, o: int) -> int:
    return b[o] << 8 | b[o + 1]


def be32(b: bytes, o: int) -> int:
    return be16(b, o) << 16 | be16(b, o + 2)


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


def ram(offset: int) -> int:
    """RAM address of a ROM offset inside the initial game state block."""
    return offset - INIT + INIT_RAM


def text(raw: bytes) -> str:
    """Game text up to the first 0: half-width kana (ESC K / ESC H = katakana on / off), ー (0x2D), Shift-JIS."""
    out, kata, i = [], False, 0
    while i < len(raw) and raw[i]:
        c = raw[i]
        if c == 0x1B:
            kata = i + 1 < len(raw) and raw[i + 1] == 0x4B
            i += 2
            continue
        if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC) and i + 1 < len(raw):
            out.append(raw[i:i + 2].decode("cp932", "replace"))
            i += 2
            continue
        if 0xA1 <= c <= 0xDF:
            ch = unicodedata.normalize("NFKC", bytes([c]).decode("cp932"))
            if c in (0xDE, 0xDF) and out:  # voiced marks combine with the previous kana
                out[-1] = unicodedata.normalize("NFC", out[-1] + ("゙" if c == 0xDE else "゚"))
                i += 1
                continue
            if not kata and "ァ" <= ch <= "ヶ":
                ch = chr(ord(ch) - 0x60)
            out.append(ch)
        elif c == 0x2D:
            out.append("ー")
        else:
            out.append(chr(c))
        i += 1
    return "".join(out)


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            return z.read(next(n for n in z.namelist() if n.lower().endswith((".md", ".bin", ".gen"))))
    with open(path, "rb") as f:
        return f.read()


def decode_tile(raw: bytes) -> list[int]:
    """32 bytes of one packed 4bpp tile -> 64 colour numbers."""
    return [raw[i // 2] >> 4 if i % 2 == 0 else raw[i // 2] & 15 for i in range(64)]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = load_rom_bytes(path)
        self._lz = self.data + koei_lz.BLOCK  # the decoder's tables, which the MD ROM doesn't have
        self._map = None

    def u16(self, o: int) -> int:
        return be16(self.data, o)

    def u32(self, o: int) -> int:
        return be32(self.data, o)

    def text_at(self, o: int) -> str:
        return text(self.data[o:o + 256])

    def records(self, at: int, count: int, size: int) -> list[bytes]:
        return [self.data[at + size * k:at + size * (k + 1)] for k in range(count)]

    def strings(self, key: str) -> list[str]:
        at, n = STRING_TABLES[key]
        return [self.text_at(self.u32(at + 4 * k)) for k in range(n)]

    # ------------------------------------------------------------ people

    def persons(self) -> list[dict]:
        out = []
        for k, r in enumerate(self.records(PERSONS, PERSON_COUNT, PERSON_SIZE)):
            first, last = self.text_at(be32(r, 0)), self.text_at(be32(r, 4))
            out.append({
                "id": k, "name": f"{first}・{last}" if last else first, "first": first, "last": last,
                "face": be16(r, 8), "stats": list(r[10:17]), "unk17": r[17], "sail_level": r[18],
                "battle_level": r[19], "sail_exp": be16(r, 20), "battle_exp": be16(r, 22), "age": r[24],
                "unk25": r[25], "unk26": r[26], "port": r[27], "unk28": r[28], "unk29": be16(r, 29),
                "country": r[31] & 15, "flags31": r[31] >> 4, "raw": r,
            })
        return out

    def vips(self) -> list[dict]:
        return [{"id": k, "name": self.text_at(be32(r, 0)), "kind": r[4], "face": r[7], "unk8": r[8], "port": r[9],
                 "raw": r} for k, r in enumerate(self.records(VIPS, VIP_COUNT, VIP_SIZE))]

    def women(self) -> list[dict]:
        return [{"id": k, "name": self.text_at(be32(r, 0)), "age": r[4], "port": r[5], "unk9": r[9], "raw": r}
                for k, r in enumerate(self.records(WOMEN, WOMAN_COUNT, WOMAN_SIZE))]

    # ------------------------------------------------------------ ships, ports, items

    def ship_types(self) -> list[dict]:
        out = []
        for k, r in enumerate(self.records(SHIP_TYPES, SHIP_TYPE_COUNT, SHIP_TYPE_SIZE)):
            spec = self.data[SHIP_SPECS + SHIP_SPEC_SIZE * k:SHIP_SPECS + SHIP_SPEC_SIZE * (k + 1)]
            out.append({"id": k, "name": self.text_at(be32(r, 0)), "number": r[4], "flags": r[5], "b6": r[6],
                        "w8": be16(r, 8), "w10": be16(r, 10), "spec": spec, "raw": r})
        return out

    def ports(self) -> list[dict]:
        out = []
        for k, r in enumerate(self.records(PORTS, PORT_COUNT, PORT_SIZE)):
            p = {"id": k, "name": self.text_at(be32(r, 4)), "x": be16(r, 0), "y": be16(r, 2), "country": r[8] & 15,
                 "flags": r[8] >> 4, "raw": r}
            if k < TRADE_PORTS:
                s = self.data[PORT_STATE + PORT_STATE_SIZE * k:PORT_STATE + PORT_STATE_SIZE * (k + 1)]
                # 32-bit numbers are stored low word first
                p.update({"unk0": s[0], "economy": be16(s, 4) << 16 | be16(s, 2),
                          "industry": be16(s, 8) << 16 | be16(s, 6), "shares": list(s[10:16]),
                          "price_levels": [c - 0x2D for c in s[16:26]], "w26": be16(s, 26), "b28": s[28],
                          "b29": s[29], "region": s[30], "items": [i for i in s[31:35] if i != 0xFF],
                          "b35": s[35], "b36": s[36], "state": s})
            out.append(p)
        return out

    def items(self) -> list[dict]:
        texts = self.strings("item_texts")
        return [{"id": k, "name": self.text_at(be32(r, 0)), "icon": r[4], "price": be16(r, 6), "power": r[8],
                 "category": r[9], "text": texts[k], "raw": r}
                for k, r in enumerate(self.records(ITEMS, ITEM_COUNT, ITEM_SIZE))]

    def discoveries(self) -> list[dict]:
        return [{"id": k, "name": n, "text": t}
                for k, (n, t) in enumerate(zip(self.strings("discovery_names"), self.strings("discovery_texts")))]

    # ------------------------------------------------------------ faces

    def portrait_tiles(self, n: int) -> bytes:
        if not 0 <= n < PORTRAIT_COUNT:
            raise IndexError(n)
        return koei_lz.decompress(self._lz, self.u32(PORTRAITS + 4 * n), len(self.data))[0][:FACE_BYTES]

    @staticmethod
    def pack_of(code: int) -> int:
        return code >> 12 & 7

    def composite_part(self, code: int, part: str) -> tuple[int, bytes]:
        """(first tile, tiles) one part of a composite face copies into the 960-byte face."""
        t = self.pack_of(code)
        _, ao, to, shift = next(p for p in COMPOSITE_PARTS if p[0] == part)
        first, count = self.u16(COMPOSITE_TILES + 0x14 * t + to), self.u16(COMPOSITE_TILES + 0x14 * t + to + 2)
        src = self.u32(COMPOSITE_ADDR + 0xA0 * t + ao + 4 * (code >> shift & 7))
        return first, self.data[src:src + 32 * count]

    def face_tiles(self, code: int) -> bytes:
        """960 bytes of 4bpp tiles the game puts in VRAM for a face code."""
        if not code & 0x8000:
            return self.portrait_tiles(code)
        if self.pack_of(code) >= COMPOSITE_PACKS:
            raise ValueError(f"no composite pack {self.pack_of(code)}")
        buf = bytearray(FACE_BYTES)
        for part, *_ in COMPOSITE_PARTS:
            first, raw = self.composite_part(code, part)
            buf[32 * first:32 * first + len(raw)] = raw
        return bytes(buf)

    def face_palette(self, at: int = FACE_PALETTE) -> list[int]:
        return [self.u16(at + 2 * i) for i in range(16)]

    def face_pixels(self, code: int) -> list[int]:
        """40 x 48 colour numbers (0-15), row-major."""
        tiles = self.face_tiles(code)
        out = [0] * (40 * 48)
        for c in range(FACE_W * FACE_H):
            cx, cy = c % FACE_W * 8, c // FACE_W * 8
            for i, v in enumerate(decode_tile(tiles[32 * c:32 * c + 32])):
                out[(cy + i // 8) * 40 + cx + i % 8] = v
        return out

    def face_rgb(self, code: int, palette: int = FACE_PALETTE) -> list[tuple[int, int, int]]:
        pal = [md_rgb(w) for w in self.face_palette(palette)]
        return [pal[v] for v in self.face_pixels(code)]

    # ------------------------------------------------------------ world map

    def map_block(self, b: int) -> bytes:
        """144 metatile values of block b (row-major 12 x 12)."""
        p = self.u32(self.u32(MAP_ROWS + 4 * (b // MAP_BLOCKS_W)) + 4 * (b % MAP_BLOCKS_W))
        return koei_lz.decompress(self._lz, p, len(self.data))[0][:MAP_BLOCK * MAP_BLOCK]

    def block_cells(self, b: int) -> bytes:
        """24 x 24 cell values of block b (0 = sea, 0x80 = plain land, other = tile number), as $3C470 writes them."""
        d, cells, n = self.data, bytearray(4 * MAP_BLOCK * MAP_BLOCK), 2 * MAP_BLOCK
        for i, v in enumerate(self.map_block(b)):
            q = d[MAP_META + 4 * v:MAP_META + 4 * v + 4] if v >= 0x10 else bytes(0x80 if v & m else 0 for m in (8, 4, 2, 1))
            y, x = i // MAP_BLOCK * 2, i % MAP_BLOCK * 2
            cells[y * n + x:y * n + x + 2] = q[:2]
            cells[(y + 1) * n + x:(y + 1) * n + x + 2] = q[2:]
        return bytes(cells)

    def map_cells(self) -> bytes:
        """MAP_W x MAP_H cell values, row-major."""
        if self._map is None:
            cells, n = bytearray(MAP_W * MAP_H), 2 * MAP_BLOCK
            for b in range(MAP_BLOCKS_W * MAP_BLOCKS_H):
                by, bx = divmod(b, MAP_BLOCKS_W)
                c = self.block_cells(b)
                for r in range(n):
                    o = (by * n + r) * MAP_W + bx * n
                    cells[o:o + n] = c[r * n:r * n + n]
            self._map = bytes(cells)
        return self._map

    def map_band(self, y: int) -> int:
        v = self.u16(MAP_BANDS + 2 * (y // (2 * MAP_BLOCK)))
        return v + 1 if v <= 4 else 9 - v
