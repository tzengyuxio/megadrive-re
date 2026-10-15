"""MD 三國志V (China, unlicensed; title screen mark "SKOB") ROM decoding.

Offsets are ROM offsets (= 68000 addresses); RAM addresses are offsets in $FF0000-$FFFFFF. See
docs/ROM_FORMAT.md. Nothing is compressed: the scenario loader at $924 copies plain per-scenario tables into RAM,
the text is a custom byte code into a 16x16 1bpp font (F0-F6 select one of 7 banks of 240 glyphs, FF ends a string)
and the 40x48 portraits are raw 4bpp tiles with one fixed palette.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
from triage import load_rom

DEFAULT_ROM = os.path.join(REPO, "roms", "San Guo Zhi V (China) (Unl).zip")
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values

# Scenarios: index = $FF60E3. The titles are on the scenario menu (drawn as graphics, not found as text); the
# start year and month are words at SCENARIO_DATES (-> RAM $6060 / $6062).
SCENARIOS = ["184年1月 黃巾之亂", "189年12月 火燒洛陽", "196年9月 曹操崛起", "201年10月 河北風雲起",
             "208年11月 臥龍出淵", "219年7月 三國鼎立", "234年9月 星落五丈原"]
SCENARIO_COUNT, SCENARIO_DATES = 7, 0xAAC
YEAR_RAM = 0x6060

# Font: pointers to 7 banks of 240 glyphs; a glyph is 32 bytes, the 8x8 quadrants TL, TR, BL, BR (8 rows each).
FONT_BANKS, BANK_SIZE, BANK_COUNT = 0xAF81C, 240, 7

# String tables: u16 offsets from the table start, then the strings.
TABLES = {"names": 0xAE4D6, "cities": 0xAE3C0, "formations": 0xAF1B6, "tactics": 0xAF202, "items": 0xAF2D8,
          "commands": 0xAF42C, "item_effects": 0xAF4E2, "messages": 0xAF652, "menus": 0xAF7CA}
NAME_COUNT = 503      # 0-499 persons, 500 憲帝 (sic, 獻帝), 501-502 民眾
PERSON_COUNT, CITY_COUNT, FORCE_COUNT, ITEM_COUNT, HELD_ITEMS = 500, 47, 20, 38, 32

# Persons: RAM $A000, 500 records of $1E bytes ($FF605A).
PERSON_RAM, PERSON_SIZE = 0xA000, 0x1E
ABILITIES = 0xA2146   # 4 bytes per person: 武力 智力 政治 魅力 (before items) -> +6..+9
PERSON_A = 0xA2916    # u16 per person -> +A (not on any screen; formation bits?)
PERSON_SCN = 0xA3C9E  # per scenario: 4 bytes per person -> +5 city, +2 status, +11 忠誠, +4 將軍職
PERSON_EXP = 0xA736A  # per scenario: 2 words per person -> +E 威名, +C 經驗值
ITEM_OWNERS = 0xAD46C  # per scenario: 32 words, owner person of item k (FFFF none) -> RAM $E8DC
ITEM_BONUS = 0x3995C  # 32 x 4 bytes: ability bonus of item k; the best holder's bonus per ability is added
STATUS = {1: "君主", 2: "太守", 3: "軍師", 4: "一般", 5: "", 6: "在野", 7: "未登場"}
NO_RANK = 0x3F

# Cities: RAM $DEE0, 47 records of $1C bytes ($FF607C).
CITY_RAM, CITY_SIZE = 0xDEE0, 0x1C
CITY_LIMITS = 0xAC1AC  # 47 x 2 words -> +16, +18 (same in all scenarios)
CITY_A = 0xAAA36       # per scenario: 4 bytes -> +B 民忠, +A 治水度, +10 訓練, +11 士氣
CITY_B = 0xAAF76       # per scenario: 3 words -> +2 太守, +8 農, +14 商
CITY_C = 0xAB748       # per scenario: 2 longs -> +C 人口, +4 士兵數
CITY_OWNERS = 0xAD648  # per scenario: 47 bytes, force of city k (FF none) -> RAM $E944

# Forces: RAM $E404, 20 records of $16 bytes ($FF6078).
FORCE_RAM, FORCE_SIZE = 0xE404, 0x16
FORCE_A = 0xAC268      # per scenario: 20 x 2 words -> +C (?), +2 (♡ on the ruler panel)
FORCE_B = 0xAC4B4      # per scenario: 20 x 2 longs -> +8 糧, +4 金
RULERS = 0xAD7B4       # per scenario: 20 words, ruler person of force k (FFFF none) -> RAM $E91C
RELATIONS = 0xAC938    # per scenario: 20 x 20 bytes -> RAM $E5BC (row force, column force; meaning unknown)
OWNERS_RAM, RULERS_RAM, ITEMS_RAM, RELATIONS_RAM = 0xE944, 0xE91C, 0xE8DC, 0xE5BC

# Portraits: 40x48, 30 raw 4bpp tiles row-major (960 bytes); n < 400 at $160000 + 960n, else $E0000 + 960(n-400)
# (routine $395E6). 0-499 = person n, 500-535 more portraits after them (not used by any person record); the
# next slot (536) has colour-0 (transparent) holes in its lower half and is left out.
FACE_W, FACE_H, FACE_BYTES, FACE_COUNT = 40, 48, 960, 536
FACE_PALETTE = 0x39800  # 16 words, CRAM line 0 (the screens' common line)

# Ruler-select map (40x28 cells): plane B nametable at MAP_NT, tiles 1-$32 from $45B20, $33-$27D from $5A48C,
# 4 palette lines at $68C4. City k's node is cell MAP_NODES[k] (word (x - 18) << 8 | (y - 17) in 8-pixel units of
# the cursor sprite; the node is the 2x2 cells from (x + 2, y + 1) of the map).
MAP_NT, MAP_W, MAP_H, MAP_PALETTE = 0x3D99A, 40, 28, 0x68C4
MAP_TILES = [(1, 0x32, 0x45B20), (0x33, 0x27D, 0x5A48C)]
MAP_NODES = 0x6BFE


def load_charset(path: str = os.path.join(HERE, "data", "charset.txt")) -> list[str]:
    """Per bank, the 240 transcribed characters (〓 = not transcribed)."""
    with open(path, encoding="utf-8") as f:
        rows = [ln.rstrip("\n") for ln in f if not ln.startswith("#")]
    return ["".join(rows[15 * b:15 * b + 15]) for b in range(BANK_COUNT)]


CHARSET = load_charset()


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.d = load_rom(path)

    def u8(self, a: int) -> int:
        return self.d[a]

    def u16(self, a: int) -> int:
        return self.d[a] << 8 | self.d[a + 1]

    def u32(self, a: int) -> int:
        return int.from_bytes(self.d[a:a + 4], "big")

    def scenario_ptr(self, table: int, s: int) -> int:
        return self.u32(table + 4 * s)

    def scenario_date(self, s: int) -> tuple[int, int]:
        return self.u16(SCENARIO_DATES + 4 * s), self.u16(SCENARIO_DATES + 4 * s + 2)

    # --- text ---
    def glyph(self, bank: int, idx: int) -> bytes:
        a = self.u32(FONT_BANKS + 4 * bank) + 32 * idx
        return self.d[a:a + 32]

    def glyph_pixels(self, bank: int, idx: int) -> list[list[int]]:
        g = self.glyph(bank, idx)
        return [[g[(y // 8) * 16 + (x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    def codes(self, a: int) -> list[tuple[int, int]]:
        """(bank, glyph) of the string at a; the bank select carries on until FF."""
        bank, out = 0, []
        while (x := self.d[a]) != 0xFF:
            a += 1
            if 0xF0 <= x <= 0xFB:
                bank = x - 0xF0
            else:
                out.append((bank, x))
        return out

    def string_codes(self, table: int, k: int) -> list[tuple[int, int]]:
        return self.codes(table + self.u16(table + 2 * k))

    def table_size(self, table: int) -> int:
        return self.u16(table) // 2

    @staticmethod
    def text(codes: list[tuple[int, int]]) -> str:
        return "".join(CHARSET[b][i] if i < BANK_SIZE else "〓" for b, i in codes)

    def strings(self, name: str) -> list[str]:
        t = TABLES[name]
        return [self.text(self.string_codes(t, k)) for k in range(self.table_size(t))]

    def names(self) -> list[str]:
        return self.strings("names")

    def city_names(self) -> list[str]:
        return self.strings("cities")

    # --- persons ---
    def item_owners(self, s: int) -> list[int]:
        a = self.scenario_ptr(ITEM_OWNERS, s)
        return [self.u16(a + 2 * k) for k in range(HELD_ITEMS)]

    def item_bonus(self, k: int) -> bytes:
        return self.d[ITEM_BONUS + 4 * k:ITEM_BONUS + 4 * k + 4]

    def base_abilities(self, p: int) -> bytes:
        return self.d[ABILITIES + 4 * p:ABILITIES + 4 * p + 4]

    def abilities(self, s: int, p: int) -> list[int]:
        """武力 智力 政治 魅力 with the items held at the start of scenario s (loader $8C44): per ability the
        largest bonus among the person's items is added; only 魅力 is capped at 100."""
        best = [0, 0, 0, 0]
        for k, owner in enumerate(self.item_owners(s)):
            if owner == p:
                best = [max(b, v) for b, v in zip(best, self.item_bonus(k))]
        out = [(a + b) & 0xFF for a, b in zip(self.base_abilities(p), best)]
        out[3] = min(out[3], 100)
        return out

    def persons(self, s: int) -> list[dict]:
        sa, ea = self.scenario_ptr(PERSON_SCN, s), self.scenario_ptr(PERSON_EXP, s)
        names, held = self.names(), self.item_owners(s)
        out = []
        for p in range(PERSON_COUNT):
            q = sa + 4 * p
            out.append({"id": p, "name": names[p], "city": self.d[q], "status": self.d[q + 1],
                        "loyalty": self.d[q + 2], "rank": self.d[q + 3], "fame": self.u16(ea + 4 * p),
                        "exp": self.u16(ea + 4 * p + 2), "base": list(self.base_abilities(p)),
                        "abilities": self.abilities(s, p), "a": self.u16(PERSON_A + 2 * p),
                        "items": [k for k, o in enumerate(held) if o == p]})
        return out

    def person_image(self, s: int) -> bytes:
        """RAM $A000-$B3A7 right after the scenario loader (fields it does not set are 0)."""
        img = bytearray(PERSON_SIZE * PERSON_COUNT)
        for p in self.persons(s):
            r = PERSON_SIZE * p["id"]
            img[r:r + 2] = p["id"].to_bytes(2, "big")
            img[r + 2], img[r + 3], img[r + 4], img[r + 5] = p["status"], 0xFF, p["rank"], p["city"]
            img[r + 6:r + 10] = bytes(p["abilities"])
            img[r + 0xA:r + 0xC] = p["a"].to_bytes(2, "big")
            img[r + 0xC:r + 0xE] = p["exp"].to_bytes(2, "big")
            img[r + 0xE:r + 0x10] = p["fame"].to_bytes(2, "big")
            img[r + 0x10], img[r + 0x11], img[r + 0x15], img[r + 0x17] = 100, p["loyalty"], 0xFF, 0xFF
        return bytes(img)

    # --- cities, forces ---
    def cities(self, s: int) -> list[dict]:
        a, b, c = (self.scenario_ptr(t, s) for t in (CITY_A, CITY_B, CITY_C))
        own = self.scenario_ptr(CITY_OWNERS, s)
        names = self.city_names()
        out = []
        for k in range(CITY_COUNT):
            out.append({"id": k, "name": names[k], "force": self.d[own + k], "governor": self.u16(b + 6 * k),
                        "farm": self.u16(b + 6 * k + 2), "trade": self.u16(b + 6 * k + 4),
                        "flood": self.d[a + 4 * k + 1], "support": self.d[a + 4 * k],
                        "training": self.d[a + 4 * k + 2], "morale": self.d[a + 4 * k + 3],
                        "population": self.u32(c + 8 * k), "soldiers": self.u32(c + 8 * k + 4),
                        "limit16": self.u16(CITY_LIMITS + 4 * k), "limit18": self.u16(CITY_LIMITS + 4 * k + 2)})
        return out

    def city_image(self, s: int) -> bytes:
        img = bytearray(CITY_SIZE * CITY_COUNT)
        for c in self.cities(s):
            r = CITY_SIZE * c["id"]
            img[r] = c["id"]
            img[r + 2:r + 4] = c["governor"].to_bytes(2, "big")
            img[r + 4:r + 8] = c["soldiers"].to_bytes(4, "big")
            img[r + 8:r + 0xA] = c["farm"].to_bytes(2, "big")
            img[r + 0xA], img[r + 0xB] = c["flood"], c["support"]
            img[r + 0xC:r + 0x10] = c["population"].to_bytes(4, "big")
            img[r + 0x10], img[r + 0x11] = c["training"], c["morale"]
            img[r + 0x14:r + 0x16] = c["trade"].to_bytes(2, "big")
            img[r + 0x16:r + 0x18] = c["limit16"].to_bytes(2, "big")
            img[r + 0x18:r + 0x1A] = c["limit18"].to_bytes(2, "big")
            img[r + 0x1A] = 0xFF
        return bytes(img)

    def forces(self, s: int) -> list[dict]:
        a, b, r = (self.scenario_ptr(t, s) for t in (FORCE_A, FORCE_B, RULERS))
        return [{"id": k, "ruler": self.u16(r + 2 * k), "heart": self.u16(a + 4 * k + 2), "unk_c": self.u16(a + 4 * k),
                 "gold": self.u32(b + 8 * k + 4), "food": self.u32(b + 8 * k)} for k in range(FORCE_COUNT)]

    def force_image(self, s: int) -> bytes:
        img = bytearray(FORCE_SIZE * FORCE_COUNT)
        for f in self.forces(s):
            r = FORCE_SIZE * f["id"]
            img[r] = f["id"]
            img[r + 2:r + 4] = f["heart"].to_bytes(2, "big")
            img[r + 4:r + 8] = f["gold"].to_bytes(4, "big")
            img[r + 8:r + 0xC] = f["food"].to_bytes(4, "big")
            img[r + 0xC:r + 0xE] = f["unk_c"].to_bytes(2, "big")
            img[r + 0xE], img[r + 0xF], img[r + 0x11], img[r + 0x12] = 0xFF, 0xFF, 0xFF, 0xFF
        return bytes(img)

    def city_owners(self, s: int) -> bytes:
        a = self.scenario_ptr(CITY_OWNERS, s)
        return self.d[a:a + CITY_COUNT]

    def rulers(self, s: int) -> list[int]:
        return [f["ruler"] for f in self.forces(s)]

    def relations(self, s: int) -> bytes:
        a = self.scenario_ptr(RELATIONS, s)
        return self.d[a:a + FORCE_COUNT * FORCE_COUNT]

    # --- graphics ---
    def palette_rgb(self, a: int, n: int = 16) -> list[tuple[int, int, int]]:
        out = []
        for i in range(n):
            w = self.u16(a + 2 * i)
            out.append((MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]))
        return out

    @staticmethod
    def face_addr(n: int) -> int:
        return 0x160000 + FACE_BYTES * n if n < 400 else 0xE0000 + FACE_BYTES * (n - 400)

    def face_raw(self, n: int) -> bytes:
        a = self.face_addr(n)
        return self.d[a:a + FACE_BYTES]

    def face_pixels(self, n: int) -> list[int]:
        raw = self.face_raw(n)
        out = []
        for y in range(FACE_H):
            for x in range(FACE_W):
                b = raw[32 * ((y // 8) * 5 + x // 8) + 4 * (y % 8) + (x % 8) // 2]
                out.append(b >> 4 if x % 2 == 0 else b & 15)
        return out

    def face_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = self.palette_rgb(FACE_PALETTE)
        return [pal[c] for c in self.face_pixels(n)]

    def map_nametable(self) -> list[int]:
        return [self.u16(MAP_NT + 2 * k) for k in range(MAP_W * MAP_H)]

    def map_tile(self, t: int) -> bytes:
        for lo, hi, a in MAP_TILES:
            if lo <= t <= hi:
                return self.d[a + 32 * (t - lo):a + 32 * (t - lo) + 32]
        return bytes(32)

    def map_rgb(self) -> tuple[int, int, list]:
        """The ruler-select map screen's plane B (320 x 224), without the dynamic text and sprites."""
        pal = self.palette_rgb(MAP_PALETTE, 64)
        w, h = MAP_W * 8, MAP_H * 8
        px = [(0, 0, 0)] * (w * h)
        for k, e in enumerate(self.map_nametable()):
            tile, line, hf, vf = self.map_tile(e & 0x7FF), e >> 13 & 3, e >> 11 & 1, e >> 12 & 1
            cx, cy = k % MAP_W, k // MAP_W
            for y in range(8):
                for x in range(8):
                    b = tile[4 * y + x // 2]
                    c = b >> 4 if x % 2 == 0 else b & 15
                    px[(cy * 8 + (7 - y if vf else y)) * w + cx * 8 + (7 - x if hf else x)] = pal[16 * line + c]
        return w, h, px

    def map_nodes(self) -> list[tuple[int, int]]:
        """City k's node: top-left map cell (column, row) of its 2x2 cells."""
        out = []
        for k in range(CITY_COUNT):
            v = self.u16(MAP_NODES + 2 * k)
            out.append(((v >> 8) + 2, (v & 0xFF) + 1))
        return out
