"""MD 大航海時代 (KOEI, 1992) ROM decoding.

The data are those of the FC / SFC versions (famicom-re/daikoukai, superfamicom-re/daikoukai) rebuilt as 68000 C
structs: big-endian, 16-bit fields word aligned, name offsets turned into 32-bit ROM pointers. The text encoding
(JIS X0201 half-width kana, ESC K / ESC H for katakana) and the face pixels are unchanged. Nothing is compressed.
See docs/ROM_FORMAT.md.
"""
import os
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_ROM = os.path.join(REPO, "roms", "Daikoukai Jidai (Japan).zip")

# ---------------------------------------------------------------- initial game state
INIT, INIT_RAM, INIT_SIZE = 0xE3E48, 0xFF1000, 0x121B   # memcpy $0688 on a new game (frame ~1770)
PERSON_START, PERSON_SIZE, PERSON_COUNT = 0x5DE, 10, 41   # RAM $FF15DE: player + 20 mates + 20 admirals
FLEET_START, FLEET_SIZE, FLEET_COUNT = 0x778, 18, 21      # RAM $FF1778: bytes 0-3 = location
PLAYER_NAME = 0xCFE                                       # RAM $FF1CFE (default レオン)
STAT_START, STAT_SIZE, STAT_COUNT = 0xD0E, 10, 21         # RAM $FF1D0E: player + 20 mates
TOWN_FLAGS = 0x112E                                       # RAM $FF212E + port: building flags
STATS = [("age", "年齡(推定)"), ("leadership", "統率"), ("judgment", "判断"), ("intelligence", "知力"),
         ("courage", "勇気"), ("strength", "強さ")]
NATION_NAMES, NATION_COUNT = 0xD76E0, 4   # BE32 name pointers ($5984): ポルトガル, イスパニア, イスラム, かいぞく
GIRL_NAMES, GIRL_COUNT = 0xE506C, 20    # 20 BE32 name pointers
GIRL_FACE = 13                          # $8266 mode 2: portrait = girl + 13

# ---------------------------------------------------------------- ports and names
PORTS, PORT_SIZE, PORT_COUNT = 0xE5946, 20, 70        # 15-byte name + chunk x, chunk y, metatile x, y + pad
PORT_INFO, PORT_INFO_SIZE, PORT_INFO_COUNT = 0xE5EBE, 6, 50  # region, specialty, ?, item, ? + pad
REGIONS = ["地中海", "北歐", "西非", "東非", "新大陸", "阿拉伯", "遠東", "東南亞"]
NAME_LISTS = {                          # key: (BE32 pointer table, count)
    "goods": (0xE653A, 26),
    "cannons": (0xE65A6, 3),
    "figureheads": (0xDA3F2, 6),
    "ships": (0xDA43A, 6),
    "woods": (0xDA482, 4),
    "masts": (0xDA492, 3),
    "sails": (0xDA49E, 2),
}

# ---------------------------------------------------------------- world map (the FC map file, little-endian)
MAP = 0xE65FA                           # = FC PRG 0x60000; $847A / $8440 read it ($858A loads an area)
MAP_AREAS_W, MAP_AREAS_H = 24, 12       # areas of 3 x 3 chunks
MAP_W, MAP_H = 72, 36                   # chunks of 7 x 7 blocks = 14 x 14 metatiles = 28 x 28 tiles
CHUNK_TILES = 28
MAP_BLOCKS = 0xD7894                    # $86E8: block -> 4 BE16 metatiles (TL, TR, BL, BR)
MAP_METATILES = 0xD7774                 # set s, metatile m at +0x48 s + 4 m: BE32 -> 4 BE16 name table words
MAP_TILESETS = 0xD7AC6                  # per set BE32 -> 72 tiles (the BE16 before them: VRAM tile 0x286)
MAP_TILE_BASE, MAP_TILE_COUNT = 0x286, 72
MAP_PALETTES = 0xD7AD6                  # $926A: per set 6 BE32 -> 16 words for CRAM line 3, by ($FF1CDA / 30) % 6
MAP_PHASES = 6
MAP_BAND = [3, 2, 1, 1, 0, 0, 0, 0, 1, 1, 2, 3]   # set ($FF3A8A) by area row, as in the FC version

# ---------------------------------------------------------------- faces (5 x 6 tiles, 4bpp packed, 960 bytes)
FACE_W, FACE_H = 5, 6
FACE_BYTES = FACE_W * FACE_H * 32
PORTRAITS, PORTRAIT_COUNT = 0x44AC6, 53  # $8068: portrait n at 0x44AC6 + 960 n
FACE_PALETTE = 0xDBF0C                  # 16 words, loaded into the face's CRAM line ($386F4)
COMPOSITE_ADDR = 0xD7F66                # $ACFC: per head 20 BE32: top x4, eyes x4, nose x4, mouth x4, bottom x4
COMPOSITE_TILES = 0xD80A6               # per head 5 x (first tile, tile count) BE16, same group order
COMPOSITE_HEADS = 4
COMPOSITE_GROUPS = ["top", "eyes", "nose", "mouth", "bottom"]
# (slot id, label, code shift) in the order $ACFC copies them; a later part overwrites whole tiles
COMPOSITE_SLOTS = [("bottom", "下", 0), ("top", "上", 8), ("eyes", "眼", 6), ("nose", "鼻", 4), ("mouth", "口", 2)]
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def be16(b: bytes, o: int) -> int:
    return b[o] << 8 | b[o + 1]


def be32(b: bytes, o: int) -> int:
    return be16(b, o) << 16 | be16(b, o + 2)


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


def text(raw: bytes) -> str:
    """Half-width kana text up to the first 0: hiragana by default, ESC K / ESC H switch katakana on / off."""
    out, kata, i = "", False, 0
    raw = raw.split(b"\0")[0]
    while i < len(raw):
        b = raw[i]
        if b == 0x1B and i + 1 < len(raw):
            kata = raw[i + 1] == 0x4B
            i += 2
            continue
        if 0xA1 <= b <= 0xDF:
            c = unicodedata.normalize("NFKC", bytes([b]).decode("cp932"))
            if not kata and "ァ" <= c <= "ヶ":
                c = chr(ord(c) - 0x60)
            out += c
        elif b == 0x2D:
            out += "ー"
        elif 0x20 <= b < 0x7F:
            out += chr(b)
        else:
            out += f"<{b:02X}>"
        i += 1
    return unicodedata.normalize("NFC", out.replace("ﾞ", "゙").replace("ﾟ", "゚"))


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            return z.read(z.namelist()[0])
    with open(path, "rb") as f:
        return f.read()


def is_composite(code: int) -> bool:
    return code > 0xFFF                 # $8266: codes above 0xFFF go to $AE36


def decode_face_code(code: int) -> tuple[int, list[int]]:
    """Composite face code -> (head, page per slot in COMPOSITE_SLOTS order)."""
    return code >> 10 & 3, [code >> shift & 3 for _, _, shift in COMPOSITE_SLOTS]


def decode_tile(raw: bytes) -> list[int]:
    """32 bytes of one packed 4bpp tile -> 64 colour numbers."""
    return [raw[i // 2] >> 4 if i % 2 == 0 else raw[i // 2] & 15 for i in range(64)]


def tiles_pixels(raw: bytes, w: int, h: int) -> bytes:
    """w x h packed 4bpp tiles stored row-major -> (8w x 8h) colour numbers."""
    out = bytearray(w * h * 64)
    for t in range(w * h):
        for i in range(64):
            b = raw[32 * t + i // 2]
            out[(t // w * 8 + i // 8) * w * 8 + t % w * 8 + i % 8] = b >> 4 if i % 2 == 0 else b & 15
    return bytes(out)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = load_rom_bytes(path)

    def u16(self, o: int) -> int:
        return be16(self.data, o)

    def u32(self, o: int) -> int:
        return be32(self.data, o)

    def text_at(self, o: int) -> str:
        return text(self.data[o:o + 64])

    def init(self, off: int, n: int) -> bytes:
        """n bytes of the initial block at INIT + off (= RAM INIT_RAM + off after a new game)."""
        return self.data[INIT + off:INIT + off + n]

    # ------------------------------------------------------------ people

    def persons(self) -> list[dict]:
        """41 person records (RAM $FF15DE): BE32 name pointer, battle, sailing level, BE16 face code, flags, pad."""
        out, nations = [], self.nations()
        for k in range(PERSON_COUNT):
            r = self.init(PERSON_START + PERSON_SIZE * k, PERSON_SIZE)
            ptr = be32(r, 0)
            # the player's name points into RAM (default レオン, part of the initial block)
            name = text(self.init(ptr - INIT_RAM, 16)) if ptr >= INIT_RAM else self.text_at(ptr)
            out.append({"id": k, "name": name, "name_ptr": ptr, "battle": r[4], "sailing": r[5],
                        "face": be16(r, 6), "nation": nations[r[8] >> 4], "flags": r[8],
                        "role": "主角" if k == 0 else "航海士" if k <= 20 else "提督"})
        for k in range(STAT_COUNT):
            r = self.init(STAT_START + STAT_SIZE * k, STAT_SIZE)
            out[k].update(zip([key for key, _ in STATS], r))
            out[k]["stat_raw"] = r[len(STATS):]
        return out

    def girls(self) -> list[dict]:
        return [{"id": k, "name": self.text_at(self.u32(GIRL_NAMES + 4 * k)), "face": k + GIRL_FACE}
                for k in range(GIRL_COUNT)]

    def fleets(self) -> list[dict]:
        """Initial fleet records (RAM $FF1778, 18 bytes): bytes 0-3 = location (chunk x/y, metatile x/y)."""
        out = []
        for k in range(FLEET_COUNT):
            r = self.init(FLEET_START + FLEET_SIZE * k, FLEET_SIZE)
            out.append({"id": k, "loc": tuple(r[:4]), "raw": r})
        return out

    # ------------------------------------------------------------ ports and names

    def nations(self) -> list[str]:
        return [self.text_at(self.u32(NATION_NAMES + 4 * i)) for i in range(NATION_COUNT)]

    def name_list(self, key: str) -> list[str]:
        o, n = NAME_LISTS[key]
        return [self.text_at(self.u32(o + 4 * i)) for i in range(n)]

    def town_flags(self, p: int) -> int:
        return self.init(TOWN_FLAGS + p, 1)[0]

    def ports(self) -> list[dict]:
        goods = self.name_list("goods")
        out = []
        for p in range(PORT_COUNT):
            o = PORTS + PORT_SIZE * p
            cx, cy, mx, my = self.data[o + 15:o + 19]
            d = {"id": p, "name": text(self.data[o:o + 15]), "chunk_x": cx, "chunk_y": cy, "mt_x": mx, "mt_y": my,
                 "supply": p >= PORT_INFO_COUNT, "flags": self.town_flags(p)}
            if p < PORT_INFO_COUNT:
                region, special, unk, item, unk4 = self.data[PORT_INFO + PORT_INFO_SIZE * p:][:5]
                d.update(region=REGIONS[region], specialty=goods[special] if special < len(goods) else "",
                         byte2=unk, item=item if item != 0xFF else "", byte4=unk4)
            out.append(d)
        return out

    # ------------------------------------------------------------ faces

    def portrait(self, n: int) -> bytes:
        """960 bytes (30 tiles, row-major 5 x 6) of portrait n."""
        if not 0 <= n < PORTRAIT_COUNT:
            raise IndexError(n)
        o = PORTRAITS + FACE_BYTES * n
        return self.data[o:o + FACE_BYTES]

    def composite_part(self, head: int, slot: str, page: int) -> tuple[int, bytes]:
        """(first tile, bytes) of one composite part: whole tiles copied into the 960-byte face."""
        g = COMPOSITE_GROUPS.index(slot)
        src = self.u32(COMPOSITE_ADDR + 0x50 * head + 0x10 * g + 4 * page)
        first, count = self.u16(COMPOSITE_TILES + 0x14 * head + 4 * g), self.u16(COMPOSITE_TILES + 0x14 * head + 4 * g + 2)
        return first, self.data[src:src + 32 * count]

    def composite(self, code: int) -> bytes:
        head, pages = decode_face_code(code)
        buf = bytearray(FACE_BYTES)
        for (slot, _, _), page in zip(COMPOSITE_SLOTS, pages):
            first, raw = self.composite_part(head, slot, page)
            buf[32 * first:32 * first + len(raw)] = raw
        return bytes(buf)

    def face(self, code: int) -> bytes:
        return self.composite(code) if is_composite(code) else self.portrait(code)

    def face_pixels(self, code: int) -> bytes:
        """40 x 48 colour numbers 0-15 (FACE_PALETTE)."""
        return tiles_pixels(self.face(code), FACE_W, FACE_H)

    def face_palette(self) -> list[int]:
        return [self.u16(FACE_PALETTE + 2 * i) for i in range(16)]

    def face_rgb(self, code: int) -> list[tuple[int, int, int]]:
        pal = [md_rgb(w) for w in self.face_palette()]
        return [pal[c] for c in self.face_pixels(code)]

    # ------------------------------------------------------------ world map

    def map_u16(self, o: int) -> int:
        return self.data[MAP + o] | self.data[MAP + o + 1] << 8

    def chunk_blocks(self, cx: int, cy: int) -> bytes:
        """7 x 7 block ids of chunk (cx, cy) ($84C2, same file layout as the FC version)."""
        area = self.map_u16(4 + 5 * (cy // 3 * MAP_AREAS_W + cx // 3))
        k = self.map_u16(self.map_u16(0) + 18 * area + 2 * (cy % 3 * 3 + cx % 3))
        o = MAP + self.map_u16(2) + 49 * k
        return self.data[o:o + 49]

    def map_set(self, cy: int) -> int:
        return MAP_BAND[cy // 3]

    def metatile_words(self, s: int, m: int) -> list[int]:
        p = self.u32(MAP_METATILES + 0x48 * s + 4 * m)
        return [self.u16(p + 2 * j) for j in range(4)]

    def chunk_words(self, cx: int, cy: int) -> list[int]:
        """28 x 28 name table words of chunk (cx, cy), as $86E8 writes them."""
        out, s = [0] * CHUNK_TILES ** 2, self.map_set(cy)
        for b, block in enumerate(self.chunk_blocks(cx, cy)):
            for q in range(4):
                words = self.metatile_words(s, self.u16(MAP_BLOCKS + 8 * block + 2 * q))
                x0, y0 = b % 7 * 4 + q % 2 * 2, b // 7 * 4 + q // 2 * 2
                for j, w in enumerate(words):
                    out[(y0 + j // 2) * CHUNK_TILES + x0 + j % 2] = w
        return out

    def map_tiles(self, s: int) -> bytes:
        p = self.u32(MAP_TILESETS + 4 * s)
        return self.data[p:p + 32 * MAP_TILE_COUNT]

    def map_palette(self, s: int, phase: int = 0) -> list[int]:
        p = self.u32(MAP_PALETTES + 0x18 * s + 4 * phase)
        return [self.u16(p + 2 * i) for i in range(16)]

    def words_pixels(self, words: list[int], w: int, tiles: bytes) -> bytes:
        """Name table words (tiles from MAP_TILE_BASE, flips honoured) -> colour numbers, 8w wide."""
        h = len(words) // w
        out = bytearray(w * h * 64)
        for i, word in enumerate(words):
            t = (word & 0x7FF) - MAP_TILE_BASE
            px = decode_tile(tiles[32 * t:32 * t + 32])
            for k, c in enumerate(px):
                x, y = k % 8, k // 8
                if word & 0x800:
                    x = 7 - x
                if word & 0x1000:
                    y = 7 - y
                out[(i // w * 8 + y) * w * 8 + i % w * 8 + x] = c
        return bytes(out)

    def chunk_pixels(self, cx: int, cy: int) -> bytes:
        """224 x 224 colour numbers of chunk (cx, cy) (palette: map_palette(map_set(cy)))."""
        return self.words_pixels(self.chunk_words(cx, cy), CHUNK_TILES, self.map_tiles(self.map_set(cy)))
