"""MD ロイヤルブラッド (KOEI, 1992) ROM decoding.

Offsets are ROM offsets (= 68000 addresses); RAM addresses are 68000 addresses ($FF0000-$FFFFFF). See
docs/ROM_FORMAT.md. The data is the FC version's (~/works/famicom-re/royal): the same 4 scenarios, the same names
and the same battle terrain, stored as 68000 C structs (big-endian words, 4-byte runtime pointers). Names are
half-width katakana (cp932 A6-DF); menu text switches to hiragana with the control code 1B 48. Nothing is
compressed.
"""
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
from triage import load_rom

DEFAULT_ROM = os.path.join(REPO, "roms", "Royal Blood (Japan).zip")
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values

# Scenarios: 4 blocks of 0x9D2 bytes; the game copies the chosen one to SCENARIO_RAM. Pointer fields (header +0,
# person +0, province +0) are 0 in the ROM and filled at run time.
SCENARIO_COUNT = 4
SCENARIO_ROM, SCENARIO_SIZE, SCENARIO_RAM = 0x30CBC, 0x9D2, 0xFF0FFC
HOUSES_AT, HOUSE_SLOTS, HOUSE_SIZE = 0x3E, 30, 4
PERSONS_AT, PERSON_COUNT, PERSON_SIZE = 0xB6, 64, 12
PROVINCES_AT, PROVINCE_COUNT, PROVINCE_SIZE = 0x3B6, 30, 52
KOEI_AT = 0x9CE                                   # "KOEI"
YEARS_AT = 0x06                                   # years since scenario 1 (0, 5, 10, 15)
SCENARIO_TITLES = (0x2DAE2, 0x2DACC, 0x2DAB8, 0x2DAA4)  # "<n>:" + menu text
STATUS = {1: "当主", 2: "家臣", 4: "在野"}
SELECT_HEADS = 0x3A038                            # 4 scenarios x 4 persons: heads of the houses a player can pick

# Name tables (functions $4E9C, $4DC0, $4F36, $50F8)
NAMES_ROM, NAME_SIZE = 0x340CE, 18                # name 14, 0, age base, unknown (2 nibbles), 0
PROVINCE_NAMES_ROM, PROVINCE_NAME_SIZE = 0x3454E, 22  # name 11, neighbours 8 (FF), map x, y, 0
UNITS_ROM, UNIT_COUNT, UNIT_SIZE = 0x347E2, 23, 20  # name 10, 0, attack?, defence?, 0, 0, strength, ?, ?, class, 0
HOUSE_NAMES_ROM, HOUSE_NAME_COUNT, HOUSE_NAME_SIZE = 0x349B4, 41, 11
UNIT_CLASS = {0x09: "怪物", 0x11: "怪物", 0x12: "傭兵", 0x0A: "魔術", 0x0C: "パスハ・ドラゴン"}

# Portraits: 40x48, 30 raw 4bpp tiles row-major (960 bytes), palette FACE_PALETTE (CRAM line 3). $6244 draws face
# n (0-63 persons = person number, 64-67 the 4 advisers) from FACES_ROM; $61A6 draws unit face n (the 23 units in
# UNITS_ROM order) from UNIT_FACES_ROM. Both load the tiles to VRAM tile $300.
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
FACES_ROM, FACE_COUNT = 0x40000, 68
ADVISER_FIRST = 64
UNIT_FACES_ROM = 0x877AC
FACE_PALETTE = 0x30C80

# Main screen: two 30x28 layouts of words (tile, palette line 2) that the game puts in the window plane ($F000, 32
# cells wide) at screen cell (1, 0); the tiles are the 0x1A1 that $2AF16 loads from MAP_TILES_ROM to VRAM tile
# MAP_TILE_BASE, palette line 2 = MAP_PALETTE. The strategy map is the 15x18 cells MAP_CELLS of the first layout
# (screen cell (16, 3), pixel (128, 24)), plain consecutive tiles; house marks and numbers are drawn over it.
# PANEL_ROM (15x19, function 0x1B of $0C16) is an empty framed panel the game draws over the map area.
SCREEN_LAYOUTS, SCREEN_W, SCREEN_H, SCREEN_AT = (0x4FF20, 0x505B0), 30, 28, (1, 0)
MAP_CELLS = (15, 3, 15, 18)                       # x, y, w, h in the layout
PANEL_ROM, PANEL_W, PANEL_H = 0x50C40, 15, 19
MAP_TILES_ROM, MAP_TILE_BASE, MAP_TILE_COUNT = 0x50F30, 0x378, 0x1A1
MAP_PALETTE = 0x30C60

# Battle maps: 30 x 10x8 terrain bytes (high nibble), the FC table byte for byte.
BATTLE_ROM, BATTLE_W, BATTLE_H = 0x34C82, 10, 8
TERRAIN = {0: "平地", 1: "?", 2: "守方本陣", 3: "攻方本陣", 4: "林", 5: "丘", 6: "山",  # names from the FC research
           12: "城門", 13: "城牆", 14: "城角(上)", 15: "城角(下)"}


def kana(b: bytes) -> str:
    """Half-width katakana name (0-terminated) as full-width."""
    return unicodedata.normalize("NFKC", b.split(b"\0")[0].decode("cp932"))


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


# Menu text: 1B 4B katakana, 1B 48 hiragana, 1B 3D x y = position; two kanji of the game's font used in titles.
MENU_KANJI = {0x8151: "家", 0x81B3: "戦"}


def menu_text(b: bytes) -> str:
    out, hira, i = [], False, 0
    while i < len(b) and b[i]:
        c = b[i]
        if c == 0x1B:
            if b[i + 1] == 0x3D:
                i += 4
                continue
            hira = b[i + 1] == 0x48
            i += 2
        elif c >= 0x80 and not 0xA1 <= c <= 0xDF:
            out.append(MENU_KANJI[int.from_bytes(b[i:i + 2], "big")])
            i += 2
        else:
            s = unicodedata.normalize("NFKC", bytes([c]).decode("cp932"))
            if hira and "ァ" <= s <= "ン":
                s = chr(ord(s) - 0x60)
            out.append(s)
            i += 1
    return "".join(out)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom(path)

    def u8(self, a: int) -> int:
        return self.data[a]

    def u16(self, a: int) -> int:
        return int.from_bytes(self.data[a:a + 2], "big")

    # --- scenarios ---
    def scenario_block(self, s: int) -> bytes:
        a = SCENARIO_ROM + SCENARIO_SIZE * s
        return self.data[a:a + SCENARIO_SIZE]

    def scenario_title(self, s: int) -> str:
        return menu_text(self.data[SCENARIO_TITLES[s]:SCENARIO_TITLES[s] + 40]).split(":", 1)[1]

    def scenario_years(self, s: int) -> int:
        return self.scenario_block(s)[YEARS_AT]

    def houses(self, s: int) -> list[dict]:
        b = self.scenario_block(s)
        out = []
        for k in range(HOUSE_SLOTS):
            r = b[HOUSES_AT + HOUSE_SIZE * k:][:HOUSE_SIZE]
            if r[0] == 0xFF:
                continue
            out.append({"slot": k, "house": r[0], "name": self.house_name(r[0]), "head": r[1], "player": r[2],
                        "flags": r[3]})
        return out

    def persons(self, s: int) -> list[dict]:
        """Persons present in scenario s (province != FF)."""
        b = self.scenario_block(s)
        out = []
        for n in range(PERSON_COUNT):
            r = b[PERSONS_AT + PERSON_SIZE * n:][:PERSON_SIZE]
            if r[7] == 0xFF:
                continue
            nm = self.name_record(n)
            out.append({"id": n, "name": nm["name"], "age": nm["age_base"] + self.scenario_years(s) + 1,
                        "int": r[4], "war": r[5], "charm": r[6], "province": r[7], "house": r[8],
                        "status": r[9], "clan": r[10], "unk11": r[11]})
        return out

    def provinces(self, s: int) -> list[dict]:
        b = self.scenario_block(s)
        out = []
        for k in range(PROVINCE_COUNT):
            r = b[PROVINCES_AT + PROVINCE_SIZE * k:][:PROVINCE_SIZE]
            w = lambda o, r=r: int.from_bytes(r[o:o + 2], "big")
            slots = [(r[o], int.from_bytes(r[o + 2:o + 4], "big"), r[o + 4]) for o in range(22, 52, 6)
                     if r[o] != 0xFF]
            out.append({"id": k, "name": self.province_name(k), "gold": w(4), "food": w(6), "soldiers": w(8),
                        "develop": r[10], "crops": r[11], "loyalty": r[12], "flags": r[13:16].hex(),
                        "owner": r[19], "units": slots})
        return out

    # --- name tables ---
    def name_record(self, n: int) -> dict:
        r = self.data[NAMES_ROM + NAME_SIZE * n:][:NAME_SIZE]
        return {"name": kana(r[:14]), "age_base": r[15], "unk16": r[16]}

    def person_name(self, n: int) -> str:
        return self.name_record(n)["name"]

    def province_name(self, k: int) -> str:
        return kana(self.data[PROVINCE_NAMES_ROM + PROVINCE_NAME_SIZE * k:][:11])

    def province_neighbours(self, k: int) -> list[int]:
        r = self.data[PROVINCE_NAMES_ROM + PROVINCE_NAME_SIZE * k + 11:][:8]
        return [v for v in r if v != 0xFF]

    def province_mark(self, k: int) -> tuple[int, int]:
        """Map cell (x, y) of the house mark, in the 15x19 map."""
        a = PROVINCE_NAMES_ROM + PROVINCE_NAME_SIZE * k + 19
        return self.data[a], self.data[a + 1]

    def house_name(self, h: int) -> str:
        return kana(self.data[HOUSE_NAMES_ROM + HOUSE_NAME_SIZE * h:][:HOUSE_NAME_SIZE])

    def units(self) -> list[dict]:
        out = []
        for n in range(UNIT_COUNT):
            r = self.data[UNITS_ROM + UNIT_SIZE * n:][:UNIT_SIZE]
            out.append({"id": n, "name": kana(r[:10]), "attack": r[11], "defence": r[12], "strength": r[15],
                        "unk16": r[16], "unk17": r[17], "class": r[18]})
        return out

    # --- graphics ---
    def palette(self, a: int) -> list[tuple[int, int, int]]:
        return [md_rgb(self.u16(a + 2 * i)) for i in range(16)]

    def face_raw(self, n: int, unit: bool = False) -> bytes:
        a = (UNIT_FACES_ROM if unit else FACES_ROM) + FACE_BYTES * n
        return self.data[a:a + FACE_BYTES]

    def face_pixels(self, n: int, unit: bool = False) -> bytes:
        """40x48 colour numbers, row by row."""
        raw = self.face_raw(n, unit)
        out = bytearray(40 * 48)
        for t in range(30):
            tx, ty = t % FACE_W, t // FACE_W
            for y in range(8):
                for x in range(8):
                    b = raw[32 * t + 4 * y + x // 2]
                    out[(ty * 8 + y) * 40 + tx * 8 + x] = b >> 4 if x % 2 == 0 else b & 15
        return bytes(out)

    def face_rgb(self, n: int, unit: bool = False) -> list[tuple[int, int, int]]:
        pal = self.palette(FACE_PALETTE)
        return [pal[c] for c in self.face_pixels(n, unit)]

    def screen_layout(self, n: int = 0) -> list[int]:
        return [self.u16(SCREEN_LAYOUTS[n] + 2 * i) for i in range(SCREEN_W * SCREEN_H)]

    def map_tile(self, t: int) -> bytes:
        """8x8 colour numbers of VRAM tile t (one of the main screen tiles)."""
        a = MAP_TILES_ROM + 32 * (t - MAP_TILE_BASE)
        raw = self.data[a:a + 32]
        return bytes(raw[i // 2] >> 4 if i % 2 == 0 else raw[i // 2] & 15 for i in range(64))

    def layout_rgb(self, words: list[int], w: int, h: int) -> tuple[int, int, list]:
        """Render w x h cells of layout words (all palette line 2 tiles of MAP_TILES_ROM)."""
        pal = self.palette(MAP_PALETTE)
        out = [(0, 0, 0)] * (w * h * 64)
        for i, word in enumerate(words):
            px = self.map_tile(word & 0x7FF)
            hf, vf = word >> 11 & 1, word >> 12 & 1
            cx, cy = i % w * 8, i // w * 8
            for k, c in enumerate(px):
                x, y = k % 8, k // 8
                x, y = (7 - x if hf else x), (7 - y if vf else y)
                out[(cy + y) * w * 8 + cx + x] = pal[c]
        return w * 8, h * 8, out

    def screen_rgb(self, n: int = 0) -> tuple[int, int, list]:
        return self.layout_rgb(self.screen_layout(n), SCREEN_W, SCREEN_H)

    def map_rgb(self) -> tuple[int, int, list]:
        x0, y0, w, h = MAP_CELLS
        lay = self.screen_layout(0)
        return self.layout_rgb([lay[(y0 + y) * SCREEN_W + x0 + x] for y in range(h) for x in range(w)], w, h)

    def panel_rgb(self) -> tuple[int, int, list]:
        return self.layout_rgb([self.u16(PANEL_ROM + 2 * i) for i in range(PANEL_W * PANEL_H)], PANEL_W, PANEL_H)

    def battle_terrain(self, k: int) -> bytes:
        a = BATTLE_ROM + BATTLE_W * BATTLE_H * k
        return bytes(v >> 4 for v in self.data[a:a + BATTLE_W * BATTLE_H])
