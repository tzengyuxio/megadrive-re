"""三国志列伝 (Sega, 1991) ROM decoding: text, names, scenarios (persons, cities, factions), portraits, map.

Two versions: the Japanese ROM and the Chinese one (三國志列傳 亂世群英), which is the same program and data moved
around, with its own font. Every function takes the ROM bytes and picks the addresses with layout(rom).
Text is 16-bit codes; glyph = high byte * 64 + low byte, into the 16x16 1bpp font (data/charset.txt,
data/charset_cn.txt). A scenario is a directory of 33 pointers that the loader at $3E28 ($3E54 in the Chinese ROM)
copies into RAM (SCENARIO_TABLES); persons are 256-slot arrays indexed by person number (the order of the name table).
"""
import os
import sys
from dataclasses import dataclass
from functools import cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from triage import load_rom

DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Sangokushi Retsuden - Ransei no Eiyuutachi (Japan).zip")
CN_ROM = os.path.join(os.path.dirname(HERE), "roms", "San Guo Zhi Lie Zhuan - Luan Shi Qun Ying (China).zip")
KANA = " アイウエオカキクケコサシセソタチツテトナハヒフヘホマモヤユヨラリルレロワンュョガギグゲゴジゼダゾデドバビブボパピペ１２３４５６７８９０スャネメ"
SCENARIO_YEARS = (189, 200, 215)


@dataclass(frozen=True)
class Layout:
    region: str             # "J" Japan, "C" China
    charset: str            # data file with the font's characters
    font: int               # 16x16 1bpp glyphs, 32 bytes each
    names: int              # 256 x 3 codes, person names
    city_names: int         # 40 x 2 codes
    readings: int | None    # 256 x 8 bytes, small-font codes (KANA), 0 = end; the Chinese version has none
    small_font: int | None  # 8x8 1bpp glyphs of KANA (8 bytes each)
    weapon_names: int       # 3 slots x 0x12 bytes: entry v (1-3) of slot s at + s*0x12 + v*6, 3 codes
    weapon_bonus: int       # attack bonus by weapon value 0-3 (the status screen takes the best of the 3 slots)
    scenario_dirs: int      # 3 x pointer to a 33-pointer directory
    loader_rts: int         # rts of the scenario loader
    city_xy: int            # 40 x (x, y) words: castle position on the strategic map in pixels
    face_map: int           # first of the portrait tables (FACE_* offsets from here)
    map_header: int         # strategic map header
    map_palettes: int       # 4 x 16 colours loaded for the map screen (line 1 entries 9 and 12 change at run time)
    map_tilesets: tuple     # (stream, dictionary, count word, first tile) as at $A1B2 (Chinese ROM $A1E0)


LAYOUTS = {
    0x89BAE: Layout("J", "charset.txt", font=0x812B8, names=0x89BAE, city_names=0x897FC, readings=0x8A2AE,
                    small_font=0x88BB8, weapon_names=0x89B72, weapon_bonus=0xB93E, scenario_dirs=0x3E1C,
                    loader_rts=0x3FF8, city_xy=0xD584A, face_map=0xAF11A, map_header=0x81276, map_palettes=0x81B6,
                    map_tilesets=((0xCF39E, 0xCF21A, 0xD4242, 0x000), (0xD211E, 0xD2076, 0xD4248, 0x200),
                                  (0xD0862, 0xD0792, 0xD4244, 0x400))),
    0x8A504: Layout("C", "charset_cn.txt", font=0x8159C, names=0x8A504, city_names=0x8A216, readings=None,
                    small_font=None, weapon_names=0x8A4C8, weapon_bonus=0xB9DE, scenario_dirs=0x3E48,
                    loader_rts=0x4024, city_xy=0xD4ACA, face_map=0xAE39A, map_header=0x8155A, map_palettes=0x81E4,
                    map_tilesets=((0xCE61E, 0xCE49A, 0xD34C2, 0x000), (0xD139E, 0xD12F6, 0xD34C8, 0x200),
                                  (0xCFAE2, 0xCFA12, 0xD34C4, 0x400))),
}
NAMES_REF = 0x9D6  # operand of a lea of the name table in both versions: tells the versions apart


def layout(rom: bytes) -> Layout:
    return LAYOUTS[int.from_bytes(rom[NAMES_REF:NAMES_REF + 4], "big")]


N_PERSONS, N_CITIES, N_FACTIONS = 256, 40, 16

# directory index → (RAM address, size, kind, field name); kinds: b = 8-bit, w = 16-bit, l = 32-bit
SCENARIO_TABLES = [
    (0xF428, 40, "b", "city_owner"),        # faction per city, 0xFF = none
    (0xF460, 80, "w", "city_governor"),     # person per city (太守), 0xFFFF = none
    (0xE640, 32, "w", "faction_ruler"),     # person per faction (君主), 0xFFFF = unused
    (0xE000, 160, "l", "city_gold"),        # 金
    (0xE0A0, 160, "l", "city_rice"),        # 米
    (0xE140, 160, "l", "city_people"),      # 民 / 1000
    (0xE1E0, 160, "l", "city_industry"),    # 産業値
    (0xE280, 160, "l", "city_e280"),
    (0xE320, 160, "l", "city_e320"),
    (0xE3C0, 160, "l", "city_e3c0"),
    (0xE460, 160, "l", "city_e460"),
    (0xE500, 160, "l", "city_e500"),
    (0xE5A0, 160, "l", "city_e5a0"),
    (0xB000, 512, "w", "hp_max"),           # 体力 (maximum)
    (0xB200, 512, "w", "hp"),               # 体力
    (0xB400, 512, "w", "war"),              # 武力
    (0xB600, 512, "w", "int"),              # 知力
    (0xB800, 512, "w", "lead"),             # 統率力
    (0xBA00, 512, "w", "p_ba00"),
    (0xBC00, 512, "w", "p_bc00"),
    (0xBE00, 512, "w", "civil"),            # 文官値
    (0xC000, 512, "w", "military"),         # 武官値
    (0xC200, 256, "b", "virtue"),           # 徳
    (0xC300, 256, "b", "loyalty"),          # 忠誠度 (rulers show —)
    (0xC400, 256, "b", "mobility"),         # 機動力
    (0xC500, 256, "b", "morale"),           # 士気
    (0xC600, 256, "b", "level"),            # レベル, 0xFF = not in this scenario
    (0xC700, 256, "b", "rank"),             # 官位 code (4 = 君主); bit 4 shows an extra title
    (0xC800, 1024, "l", "soldiers"),        # 兵力
    (0xCC00, 256, "b", "city"),             # city number (1-based), 0 = none
    (0xE710, 32, "w", "e710"),
    (0xEA88, 768, "3", "weapons"),          # 3 weapon slots (ROM keeps slot 1, slot 0, slot 2)
    (0xF000, 512, "w", "f000"),             # stored as words; the loader keeps value - 0xB8 as a byte
]


@cache
def charset(name: str = "charset.txt") -> str:
    with open(os.path.join(HERE, "data", name), encoding="utf-8") as fh:
        return "".join(line.rstrip("\n") for line in fh if not line.startswith("#"))


@cache
def _index(cs: str) -> dict[str, int]:
    return {c: i for i, c in reversed(list(enumerate(cs)))}


CHARSET = charset()


def code_of(glyph: int) -> int:
    """16-bit text code of a glyph number: high byte = glyph // 64, low byte = glyph % 64."""
    return (glyph // 64) << 8 | glyph % 64


def glyph_of(code: int) -> int:
    return (code >> 8) * 64 + (code & 0xFF)


def encode(s: str, cs: str = CHARSET) -> bytes:
    index = _index(cs)
    return b"".join(code_of(index[c]).to_bytes(2, "big") for c in s)


def decode(b: bytes, cs: str = CHARSET) -> str:
    out = []
    for i in range(0, len(b) - 1, 2):
        g = glyph_of(b[i] << 8 | b[i + 1])
        out.append(cs[g] if g < len(cs) else f"<{b[i]:02X}{b[i + 1]:02X}>")
    return "".join(out)


def text(rom: bytes, a: int, n: int) -> str:
    """n codes at a, in the charset of rom's version."""
    return decode(rom[a:a + 2 * n], charset(layout(rom).charset))


def load(path: str = DEFAULT_ROM) -> bytes:
    return load_rom(path)


def names(rom: bytes) -> list[str]:
    a = layout(rom).names
    return [text(rom, a + i * 6, 3).rstrip("　") for i in range(N_PERSONS)]


def readings(rom: bytes) -> list[str]:
    """Katakana readings of the status screen; empty strings for the Chinese version (it has none)."""
    a = layout(rom).readings
    if a is None:
        return [""] * N_PERSONS
    return ["".join(KANA[c] for c in rom[a + i * 8:a + i * 8 + 8] if c) for i in range(N_PERSONS)]


def city_xy(rom: bytes) -> list[tuple[int, int]]:
    """Castle positions ($674DC draws the flags)."""
    w = _words(rom, layout(rom).city_xy, 2 * N_CITIES)
    return [(w[2 * i], w[2 * i + 1]) for i in range(N_CITIES)]


def city_names(rom: bytes) -> list[str]:
    a = layout(rom).city_names
    return [text(rom, a + i * 4, 2) for i in range(N_CITIES)]


def weapon_name(rom: bytes, slot: int, value: int) -> str:
    return text(rom, layout(rom).weapon_names + slot * 0x12 + value * 6, 3).rstrip("　")


def scenario_pointers(rom: bytes, n: int) -> list[int]:
    a = layout(rom).scenario_dirs
    d = int.from_bytes(rom[a + 4 * n:a + 4 * n + 4], "big")
    return [int.from_bytes(rom[d + 4 * k:d + 4 * k + 4], "big") for k in range(len(SCENARIO_TABLES))]


def _values(b: bytes, kind: str) -> list:
    if kind == "b":
        return list(b)
    if kind == "3":  # slot order as in RAM: the loader swaps the first two bytes
        return [(b[i + 1], b[i], b[i + 2]) for i in range(0, len(b), 3)]
    w = {"w": 2, "l": 4}[kind]
    return [int.from_bytes(b[i:i + w], "big") for i in range(0, len(b), w)]


def scenario(rom: bytes, n: int) -> dict[str, list]:
    """Every table of scenario n (0-2) as {field: values}, values as stored in ROM."""
    out = {}
    for p, (_, size, kind, field) in zip(scenario_pointers(rom, n), SCENARIO_TABLES):
        out[field] = _values(rom[p:p + size], kind)
    return out


def ram_image(rom: bytes, n: int) -> dict[int, bytes]:
    """{RAM address: bytes} the loader at $3E28 writes for scenario n (for comparison with a RAM dump)."""
    out = {}
    for p, (addr, size, kind, field) in zip(scenario_pointers(rom, n), SCENARIO_TABLES):
        b = rom[p:p + size]
        if field == "weapons":
            b = b"".join(bytes([b[i + 1], b[i], b[i + 2]]) for i in range(0, size, 3))
        elif field == "f000":
            b = bytes(0xFF if v == 0xFFFF else (v - 0xB8) & 0xFF for v in _values(b, "w"))
        out[addr] = b
    return out


def attack(war: int, morale: int, weapons: tuple[int, int, int], rom: bytes) -> tuple[int, int]:
    """The two 攻撃力 numbers of the status screen ($B8B8, $B8E2)."""
    bonus = max(rom[layout(rom).weapon_bonus + v] for v in weapons)
    return war * morale // 100, war + bonus


# Portraits ($65C22, D0 = person number; Chinese ROM $661D4): 6x8 tiles, plus eye and mouth overlays. The tables
# follow each other at these offsets from Layout.face_map (Japanese ROM $AF11A, Chinese ROM $AE39A):
FACE_MAP = 0           # 256 x 48 tile numbers (words)
FACE_EYES = 0x6000     # 256 x 8: eyes open (4 tiles), eyes closed (4) - a 4x1 sprite at tile (1, 3)
FACE_MOUTH = 0x7000    # 256 x 4: mouth closed (2 tiles), mouth open (2) - nametable cells (2, 5) and (3, 5)
FACE_PALETTES = 0x7600  # 16 colours (MD words) per palette
FACE_PAL_INDEX = 0x8000  # 256 bytes → palette number
FACE_TILES = 0x8100    # 4bpp tiles, 32 bytes each
N_FACES, FACE_W, FACE_H = 256, 6, 8
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def _words(rom: bytes, a: int, n: int) -> list[int]:
    return [int.from_bytes(rom[a + 2 * k:a + 2 * k + 2], "big") for k in range(n)]


def face_palette(rom: bytes, n: int) -> list[int]:
    """16 MD colour words (0000BBB0GGG0RRR0) of portrait n."""
    f = layout(rom).face_map
    return _words(rom, f + FACE_PALETTES + rom[f + FACE_PAL_INDEX + n] * 32, 16)


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


def _tile(rom: bytes, t: int) -> list[list[int]]:
    a = layout(rom).face_map + FACE_TILES + t * 32
    d = rom[a:a + 32]
    return [[d[y * 4 + x // 2] >> (4 if x % 2 == 0 else 0) & 15 for x in range(8)] for y in range(8)]


def face_pixels(rom: bytes, n: int, eyes: int = 0, mouth: int = 0) -> list[list[int]]:
    """48x64 colour indices of portrait n as the status screen shows it: eyes 0 = open / 1 = closed,
    mouth 0 = closed / 1 = open. Colour 0 of the eye sprite is transparent."""
    f = layout(rom).face_map
    tiles = _words(rom, f + FACE_MAP + n * 96, 48)
    mouth_tiles = _words(rom, f + FACE_MOUTH + n * 8, 4)
    tiles[5 * 6 + 2], tiles[5 * 6 + 3] = mouth_tiles[mouth * 2:mouth * 2 + 2]
    px = [[0] * (FACE_W * 8) for _ in range(FACE_H * 8)]
    for k, t in enumerate(tiles):
        for y, row in enumerate(_tile(rom, t)):
            px[k // 6 * 8 + y][k % 6 * 8:k % 6 * 8 + 8] = row
    for k, t in enumerate(_words(rom, f + FACE_EYES + n * 16 + eyes * 8, 4)):
        for y, row in enumerate(_tile(rom, t)):
            for x, c in enumerate(row):
                if c:
                    px[24 + y][8 + k * 8 + x] = c
    return px


def unpack_words(rom: bytes, src: int, dictionary: int, count: int) -> list[int]:
    """The word stream decoder at $AD48 (Chinese ROM $ADFC; writes to the VDP data port): count = stream words - 1. A word below
    $FE00 is output as is; $FEnn outputs dictionary entry nn (2 words at dictionary + 4*nn, or just its first word
    when that is itself a $FExx code); $FFnn repeats the next word (a dictionary reference gives its first word,
    and its second word follows) nn + 1 times."""
    def word(a: int) -> int:
        return int.from_bytes(rom[a:a + 2], "big")

    out, pending, d0 = [], [], count
    while True:
        if pending:
            w = pending.pop(0)
        else:
            w = word(src)
            src += 2
            d0 -= 1
        if w >= 0xFF00:
            n = w & 0xFF
            if pending:
                v = pending.pop(0)
            else:
                v = word(src)
                src += 2
                d0 -= 1
            if 0xFE00 <= v < 0xFF00:
                e = dictionary + (v & 0xFF) * 4
                v = word(e)
                pending = [word(e + 2)]
            out += [v] * (n + 1)
        elif w >= 0xFE00:
            e = dictionary + (w & 0xFF) * 4
            first = word(e)
            if 0xFE00 <= first < 0xFF00:
                out.append(first)
                continue
            pending = [first, word(e + 2)]
            continue
        else:
            out.append(w)
        if not pending and d0 < 0:
            return out


# Strategic map: header at Layout.map_header ($AEB0 reads it) - word block rows (4), byte block height (24 rows),
# byte block width (40 tiles), long base, then a word offset per block (block = row * 4 + column... in the order
# index = y_block * 4 + x_block). A block is a long pointer to its data and 25 word offsets (24 rows + end); a row
# is 40 nametable words where a word whose low 11 bits are $6FF + n (n = 1-127, bit 7 of n = count up) repeats the
# next word n times.


def map_row(rom: bytes, a: int, end: int) -> list[int]:
    out = []
    while a < end:
        w = int.from_bytes(rom[a:a + 2], "big")
        a += 2
        n = (w & 0x7FF) - 0x6FF
        if n < 0:
            out.append(w)
            continue
        t = int.from_bytes(rom[a:a + 2], "big")
        a += 2
        out += [t + k if n & 0x80 else t for k in range(n & 0x7F)]
    return out


def strategic_map(rom: bytes) -> list[list[int]]:
    """Nametable words of the whole strategic map (144 rows x 160 columns)."""
    h = layout(rom).map_header
    rows_of_blocks, bh, bw = int.from_bytes(rom[h:h + 2], "big"), rom[h + 2], rom[h + 3]
    base = int.from_bytes(rom[h + 4:h + 8], "big")
    n_blocks = 0
    while int.from_bytes(rom[h + 8 + 2 * n_blocks:h + 10 + 2 * n_blocks], "big") != 0xFFFF:
        n_blocks += 1
    cols_of_blocks = n_blocks // rows_of_blocks
    grid = [[0] * (rows_of_blocks * bw) for _ in range(cols_of_blocks * bh)]
    for k in range(n_blocks):
        d = base + int.from_bytes(rom[h + 8 + 2 * k:h + 10 + 2 * k], "big")
        p = int.from_bytes(rom[d:d + 4], "big")
        offs = [int.from_bytes(rom[d + 4 + 2 * r:d + 6 + 2 * r], "big") for r in range(bh + 1)]
        by, bx = divmod(k, rows_of_blocks)
        for r in range(bh):
            row = map_row(rom, p + offs[r], p + offs[r + 1])
            grid[by * bh + r][bx * bw:bx * bw + bw] = row
    return grid


def map_tiles(rom: bytes) -> dict[int, bytes]:
    """{tile number: 32 bytes} of the map screen's tile sets."""
    out = {}
    for src, dic, cnt, first in layout(rom).map_tilesets:
        words = unpack_words(rom, src, dic, int.from_bytes(rom[cnt:cnt + 2], "big"))
        data = b"".join(w.to_bytes(2, "big") for w in words)
        for k in range(len(data) // 32):
            out[first + k] = data[k * 32:k * 32 + 32]
    return out


def map_palettes(rom: bytes) -> list[list[int]]:
    return [_words(rom, layout(rom).map_palettes + 32 * k, 16) for k in range(4)]


def render_nametable(grid: list[list[int]], tiles: dict[int, bytes], palettes: list[list[int]]) -> list[list[tuple]]:
    """RGB rows of a grid of nametable words (flip bits honoured; palette = bits 13-14)."""
    h, w = len(grid) * 8, len(grid[0]) * 8
    out = [[(0, 0, 0)] * w for _ in range(h)]
    blank = bytes(32)
    for gy, row in enumerate(grid):
        for gx, e in enumerate(row):
            d = tiles.get(e & 0x7FF, blank)
            pal = palettes[e >> 13 & 3]
            for y in range(8):
                sy = 7 - y if e & 0x1000 else y
                for x in range(8):
                    sx = 7 - x if e & 0x800 else x
                    c = d[sy * 4 + sx // 2] >> (4 if sx % 2 == 0 else 0) & 15
                    out[gy * 8 + y][gx * 8 + x] = md_rgb(pal[c])
    return out
