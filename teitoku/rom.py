"""MD 提督の決断 (KOEI, 1992) ROM decoding.

Offsets are ROM offsets (= 68000 addresses); RAM addresses are offsets in $FF0000-$FFFFFF. See docs/ROM_FORMAT.md.
The game is the SFC version (~/works/superfamicom-re/teitoku) rewritten in 68000 C: same tables and text encoding
(the SFC font, glyph codes 0x8140 + g, JIS X 0201 kana with ESC K / ESC H), records widened and big-endian. The
faces are KOEI LZ streams (tools/koei_lz.py; the MD decoder has no lookup tables, so the SFC table block is
appended to the ROM image for decoding).
"""
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz
from triage import load_rom

DEFAULT_ROM = os.path.join(REPO, "roms", "Teitoku no Ketsudan (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

# ---------------------------------------------------------------- text
# Font: 1036 glyphs of 16x16 1bpp (32 bytes: top-left, top-right, bottom-left, bottom-right 8x8) at FONT, the SFC
# font (glyph 1035 differs). Two-byte code 0x8140 + g; 0x9140 + k stands for 0x8200 + 0x100 k. One-byte codes:
# ASCII, JIS X 0201 kana drawn as hiragana or, after ESC K, katakana (ESC H back); ESC F toggles date glyphs.
FONT = 0x53386
GLYPH_COUNT = 1036
DATE_GLYPHS = {"0": "年", "1": "月", "2": "日"}

# ---------------------------------------------------------------- initialised data and scenarios
# The C runtime copies DATA_ROM to RAM DATA_RAM (DATA_SIZE bytes, memmove $4DB8 called from $39F6); a new game copies
# it again. Scenario 1 is this image; the loader $10B46 patches it for scenarios 2-9 from the uncompressed record
# SCENARIO_PATCHES[s] (ROM pointer table, indexed by scenario number).
DATA_ROM, DATA_RAM, DATA_SIZE = 0x7A9B6, 0x0060, 0x3F89
DATA_END = DATA_RAM + DATA_SIZE
SCENARIO_COUNT = 9
SCENARIO_PATCHES = 0x60EA2
SCENARIO_MENU = 0x60DD6          # 9 pointers to "n:title  Syy.mm.dd"
LOADER, LOADER_DONE = 0x10B46, 0x10FCC

# RAM tables: address, record size, count
SHIPS, SHIP_SIZE, SHIP_COUNT = 0x0C0C, 22, 270
BASES, BASE_SIZE, BASE_COUNT = 0x2356, 74, 50
FLEETS, FLEET_SIZE, FLEET_COUNT = 0x3214, 54, 32
SIDES, SIDE_SIZE = 0x38D4, 68
ADMIRALS, ADMIRAL_SIZE, ADMIRAL_COUNT = 0x395C, 36, 40
COUNTRIES, COUNTRY_SIZE = 0x3EFC, 16
SCENARIO_DATE = 0x0074           # three words: Showa year, month, day
SCENARIO_NUMBER = (0x0062, 0x0064)  # words set to the chosen scenario by the menu ($110D6) before the loader

SHIP_TYPE_NAMES = 0x5B546        # 16 long pointers, types 7 and 11 unused
BASE_NAMES = 0x7EBC8             # 50 x (name pointer, two-letter code pointer)
ALLIANCE = {1: "日本", 2: "連合", 3: "中立"}
SIDE_NAMES = ["日本軍", "連合国軍"]

# Faces ($9E00(admiral pointer, x, y, face)): face n = admiral index for an admiral, else the argument; 0x2A / 0x31
# add 0 or 2 and 0x2B / 0x32 add 0, 2 or 3 at random. 54 KOEI LZ streams of 960 bytes (5 x 6 tiles, row by row) at
# FACE_POINTERS; palette = FACE_PALETTES + 32 * FACE_PAL[n] (word), loaded to CRAM line 3.
FACE_POINTERS = 0xAAB34
FACE_PALETTES = 0x5C41E
FACE_PAL = 0x5FCD8
FACE_COUNT, FACE_W, FACE_H, FACE_BYTES = 54, 5, 6, 960
# Faces 40-53 are nobody's; they appear in scenes (meetings, reports). Unnamed in the ROM; grouped by uniform as in
# the SFC version (its faces 20-26 / 47-53, in the same order except SFC 23 / 24 and 50 / 51 swapped).
OTHER_FACES = {40: "陸軍", 41: "海軍", 42: "陸軍", 43: "飛行員", 44: "陸軍", 45: "飛行員", 46: "飛行員",
               47: "陸軍", 48: "海軍", 49: "海軍", 50: "飛行員", 51: "海軍", 52: "飛行員", 53: "飛行員"}
# World map (situation / victory screens, $9100, $FBC6, $39AC0): WORLD_TILE_COUNT uncompressed 4bpp tiles at
# WORLD_TILES loaded to tile WORLD_TILE0, then the WORLD_W x WORLD_H tilemap words at WORLD_TILEMAP (palette line 2,
# tile numbers absolute) put on plane B; palette WORLD_PALETTE (32 bytes) in CRAM line 2.
WORLD_TILES, WORLD_TILE0, WORLD_TILE_COUNT = 0x890EA, 0x580, 0x140
WORLD_TILEMAP, WORLD_W, WORLD_H = 0xD973A, 32, 16
WORLD_PALETTE = 0x5C21E
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def be16(raw, o: int) -> int:
    return raw[o] << 8 | raw[o + 1]


def be32(raw, o: int) -> int:
    return int.from_bytes(raw[o:o + 4], "big")


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


def load_charset(path: str = CHARSET) -> str:
    with open(path, encoding="utf-8") as f:
        cs = "".join(line.rstrip("\n") for line in f if not line.startswith("#"))
    assert len(cs) == GLYPH_COUNT, len(cs)
    return cs


def _kana(c: int, katakana: bool) -> str:
    s = unicodedata.normalize("NFKC", bytes([c]).decode("cp932"))
    if not katakana and "ァ" <= s <= "ヶ":
        s = chr(ord(s) - 0x60)
    return s


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
        self.charset = load_charset()
        self._lz = self.data + koei_lz.BLOCK
        self._faces: dict[int, bytes] = {}

    def u16(self, o: int) -> int:
        return be16(self.data, o)

    def u32(self, o: int) -> int:
        return be32(self.data, o)

    # ------------------------------------------------------------ text
    def text(self, raw: bytes, i: int = 0) -> str:
        """Game string -> str, up to NUL. Unknown control bytes become [xx]."""
        out, kata, date = [], False, False
        while i < len(raw) and raw[i]:
            c = raw[i]
            if 0x81 <= c <= 0x9F or c >= 0xE0:
                code = c << 8 | raw[i + 1]
                if code >= 0x9140:
                    code = 0x8200 + ((code - 0x9140) << 8)
                out.append(self.charset[code - 0x8140 if code <= 0x854C else 0])
                i += 2
                continue
            if c == 0x1B:
                k = chr(raw[i + 1])
                if k in "KH":
                    kata = k == "K"
                elif k == "F":
                    date = not date
                else:
                    out.append(f"[1b{raw[i + 1]:02x}]")
                i += 2
                continue
            if date and chr(c) in DATE_GLYPHS:
                out.append(DATE_GLYPHS[chr(c)])
            elif 0xA1 <= c <= 0xDF:
                out.append(_kana(c, kata))
            elif 0x20 <= c < 0x7F or c in (0x0A, 0x09):
                out.append(chr(c))
            else:
                out.append(f"[{c:02x}]")
            i += 1
        return unicodedata.normalize("NFC", "".join(out))  # kana + combining (han)dakuten

    def string(self, addr: int) -> str:
        return self.text(self.data, addr)

    def glyph(self, g: int) -> list[list[int]]:
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    # ------------------------------------------------------------ RAM images
    def data_image(self) -> bytearray:
        """RAM $FF0000-$FFFFFF after the data copy (only DATA_RAM-DATA_END filled)."""
        img = bytearray(0x10000)
        img[DATA_RAM:DATA_END] = self.data[DATA_ROM:DATA_ROM + DATA_SIZE]
        return img

    def scenario_image(self, sc: int) -> bytearray:
        """RAM right after the loader ($10B46) for scenario sc (1-9), with the scenario number the menu set."""
        img = self.data_image()
        for o in SCENARIO_NUMBER:
            img[o:o + 2] = sc.to_bytes(2, "big")
        if sc < 2:
            return img
        s = self.data[self.u32(SCENARIO_PATCHES + 4 * sc):]
        w16 = lambda o, v: img.__setitem__(slice(o, o + 2), (v & 0xFFFF).to_bytes(2, "big"))
        w32 = lambda o, v: img.__setitem__(slice(o, o + 4), v.to_bytes(4, "big"))
        for i in range(SHIP_COUNT):  # ships: 16 bytes each
            r, d = s[16 * i:16 * i + 16], SHIPS + SHIP_SIZE * i
            img[d + 5] = r[0]
            img[d + 0x0A:d + 0x11] = r[5:0x0C]
            w16(d + 0x14, be16(img, d + 0x14) & 0xB800 | be16(r, 0x0E))
        for i in range(FLEET_COUNT):  # fleets: 28 bytes each
            r, d = s[0x10E0 + 28 * i:0x10E0 + 28 * i + 28], FLEETS + FLEET_SIZE * i
            img[d:d + 2] = r[0:2]
            if be16(r, 0) & 0x8000:  # unused fleet
                img[d + 2:d + 8] = b"\xff" * 6
                for o, n in ((8, 2), (0x0C, 8), (0x16, 2), (0x1A, 4), (0x1E, 5), (0x33, 3)):
                    img[d + o:d + o + n] = bytes(n)
                continue
            img[d + 2:d + 10] = r[2:10]
            if be16(r, 0x0A):
                w32(d + 0x0C, 0xFF0000 + ADMIRALS - ADMIRAL_SIZE + i // 16 * 20 * ADMIRAL_SIZE
                    + be16(r, 0x0A) * ADMIRAL_SIZE)
            img[d + 0x10:d + 0x14] = r[0x0C:0x10]
            img[d + 0x16:d + 0x18] = r[0x10:0x12]
            w32(d + 0x1A, 0xFF0000 + SHIPS + SHIP_SIZE * be16(r, 0x12))
            img[d + 0x1E:d + 0x23] = r[0x14:0x19]
            img[d + 0x33] = r[0x19]
            img[d + 0x34:d + 0x36] = r[0x1A:0x1C]
        for i in range(BASE_COUNT):  # bases: 38 bytes each
            r, d = s[0x1460 + 38 * i:0x1460 + 38 * i + 38], BASES + BASE_SIZE * i
            img[d + 1:d + 6] = r[0:5]
            img[d + 6:d + 0x1A] = r[6:0x1A]
            img[d + 0x26] = r[0x1A]
            img[d + 0x2B:d + 0x2E] = r[0x1B:0x1E]
            if img[d + 0x29] == 0:
                img[d + 0x2D] = 0x32
            img[d + 0x40:d + 0x46] = r[0x1E:0x24]
            w16(d + 0x48, be16(img, d + 0x48) & 0x3800 | be16(r, 0x24))
        for i in range(2):  # sides: 52 bytes each
            r, d = s[0x1BCC + 52 * i:0x1BCC + 52 * i + 52], SIDES + SIDE_SIZE * i
            img[d + 8:d + 0x1A] = r[0:0x12]
            img[d + 0x1A:d + 0x22] = r[0x12:0x1A]
            img[d + 0x22:d + 0x28] = r[0x1A:0x20]
            img[d + 0x28:d + 0x2F] = r[0x20:0x27]
            for k, o in enumerate((0x30, 0x34, 0x38)):
                w32(d + o, 0xFF0000 + BASES + BASE_SIZE * be16(r, 0x28 + 2 * k))
            img[d + 0x3C] = r[0x2E]
            img[d + 0x3E:d + 0x40] = r[0x30:0x32]
            img[d + 0x42] = r[0x32]
        img[SCENARIO_DATE:SCENARIO_DATE + 6] = s[0x1C34:0x1C3A]
        for i in range(ADMIRAL_COUNT):
            img[ADMIRALS + ADMIRAL_SIZE * i + 0x22] |= s[0x1C3A + i]
        p, d = 0x1C62, COUNTRIES
        while be32(img, d):  # countries: 12 bytes each, up to the record whose name pointer is 0
            r = s[p:p + 12]
            img[d + 4:d + 9] = r[0:5]
            for k in range(5):
                img[d + 9 + k] = min(r[5 + k], 0x63)
            if img[d + 0x0C] >= 0x50:
                img[d + 0x0E] |= 1
            if img[d + 0x0C] >= 0x5F:
                img[d + 0x0E] |= 2
            if img[d + 0x0C] >= 0x50 and img[d + 0x0D] >= 0x50:
                img[d + 0x0E] |= 8
            p += 12
            d += COUNTRY_SIZE
        for side in range(2):  # each side's headquarters base (+0x3C, 1-based): +0x46 = 2
            img[BASES + BASE_SIZE * (img[SIDES + SIDE_SIZE * side + 0x3C] - 1) + 0x46] = 2
        return img

    # ------------------------------------------------------------ tables
    def type_names(self) -> list[str]:
        return [self.string(p) if (p := self.u32(SHIP_TYPE_NAMES + 4 * t)) else "" for t in range(16)]

    def base_name(self, i: int) -> tuple[str, str]:
        return self.string(self.u32(BASE_NAMES + 8 * i)), self.string(self.u32(BASE_NAMES + 8 * i + 4))

    def scenarios(self) -> list[dict]:
        out = []
        for sc in range(1, SCENARIO_COUNT + 1):
            num_title, date = self.string(self.u32(SCENARIO_MENU + 4 * (sc - 1))).split(None, 1)
            img = self.scenario_image(sc)
            y, m, d = (be16(img, SCENARIO_DATE + 2 * k) for k in range(3))
            out.append({"id": sc, "title": num_title.split(":", 1)[1], "date_text": date.replace(" ", ""),
                        "date": f"{1925 + y}-{m:02d}-{d:02d}", "showa": y})
        return out

    def elapsed_months(self, sc: int) -> int:
        """Months from 1941-11 to the start of scenario sc (the game lowers ship +12 by this at the start, $10FD2)."""
        img = self.scenario_image(sc)
        return be16(img, SCENARIO_DATE) * 12 + be16(img, SCENARIO_DATE + 2) - (16 * 12 + 11)

    def ships(self, sc: int = 1) -> list[dict]:
        img, names, elapsed = self.scenario_image(sc), self.type_names(), self.elapsed_months(sc)
        out = []
        for i in range(SHIP_COUNT):
            b = img[SHIPS + SHIP_SIZE * i:SHIPS + SHIP_SIZE * (i + 1)]
            name, _, reading = self.string(be32(b, 0)).partition(" ")
            f = be16(b, 0x14)
            out.append({
                "id": i, "name": name, "reading": reading, "side": f >> 15, "type": b[4], "type_name": names[b[4]],
                "fleet": b[5], "anti_ship": b[6], "anti_air": b[7], "armor": b[8], "speed": b[9], "capacity": b[0x0A],
                "fighters": b[0x0B], "attackers": b[0x0C], "scouts": b[0x0D], "troops": b[0x0E], "unk_0f": b[0x0F],
                "unk_10": b[0x10], "unk_11": b[0x11], "complete_month": b[0x12], "class": b[0x13],
                "building": int(bool(f & 4) and b[0x12] > elapsed), "sunk": f & 1, "flags": f})
        return out

    def bases(self, sc: int = 1) -> list[dict]:
        img = self.scenario_image(sc)
        out = []
        for i in range(BASE_COUNT):
            b = img[BASES + BASE_SIZE * i:BASES + BASE_SIZE * (i + 1)]
            name, code = self.base_name(i)
            out.append({
                "id": i, "name": name, "code": code, "owner": b[1], "armament_max": b[2],
                "durability_max": b[3], "armament": b[4], "durability": b[5], "fighters": be16(b, 6),
                "attackers": be16(b, 8), "scouts": be16(b, 0x0A), "twin_engine": be16(b, 0x0C),
                "rockets": be16(b, 0x0E), "large_planes": be16(b, 0x10), "fuel": be32(b, 0x12),
                "materials": be16(b, 0x16), "troops": be16(b, 0x18), "x": be16(b, 0x22), "y": be16(b, 0x24),
                "unk_26": b[0x26], "iron": b[0x27], "oil": b[0x28], "population": b[0x29], "industry": b[0x2A],
                "troop_ships": b[0x2B], "fuel_ships": b[0x2C], "friendship": b[0x2D], "hq": int(b[0x46] == 2),
                "flags": be16(b, 0x48), "raw": bytes(b).hex()})
        return out

    def fleets(self, sc: int = 1) -> list[dict]:
        img = self.scenario_image(sc)
        out = []
        for i in range(FLEET_COUNT):
            b = img[FLEETS + FLEET_SIZE * i:FLEETS + FLEET_SIZE * (i + 1)]
            if be16(b, 0) & 0x8000:
                continue
            adm = be32(b, 0x0C)
            out.append({
                "id": i, "side": i // 16, "number": b[0x0A], "x": be16(b, 0), "y": be16(b, 2), "dest_x": be16(b, 4),
                "dest_y": be16(b, 6), "base": b[8] - 1,
                "admiral": (adm - 0xFF0000 - ADMIRALS) // ADMIRAL_SIZE if adm else -1, "fuel": be32(b, 0x10),
                "morale": b[0x16], "fatigue": b[0x17], "fuel_ships": b[0x1E],
                "troop_ships": [v & 0x7F for v in b[0x1F:0x23] if v & 0x80],
                "flagship": (be32(b, 0x1A) - 0xFF0000 - SHIPS) // SHIP_SIZE, "raw": bytes(b).hex()})
        return out

    def sides(self, sc: int = 1) -> list[dict]:
        img = self.scenario_image(sc)
        return [{"id": i, "name": self.text(bytes(img[SIDES + SIDE_SIZE * i:SIDES + SIDE_SIZE * (i + 1)]), 1),
                 "hq": img[SIDES + SIDE_SIZE * i + 0x3C] - 1,
                 "raw": bytes(img[SIDES + SIDE_SIZE * i:SIDES + SIDE_SIZE * (i + 1)]).hex()} for i in range(2)]

    def admirals(self, sc: int = 1) -> list[dict]:
        img = self.scenario_image(sc)
        out = []
        for i in range(ADMIRAL_COUNT):
            b = img[ADMIRALS + ADMIRAL_SIZE * i:ADMIRALS + ADMIRAL_SIZE * (i + 1)]
            f = b[0x22]
            out.append({"id": i, "name": self.text(bytes(b)), "side": i // 20, "face": i, "fleet": f & 0x1F,
                        "absent": f >> 7, "foreign": f >> 5 & 3, "flags": f})
        return out

    def countries(self, sc: int = 1) -> list[dict]:
        img = self.scenario_image(sc)
        out, d = [], COUNTRIES
        while be32(img, d):
            b = img[d:d + COUNTRY_SIZE]
            out.append({"id": len(out), "name": self.string(be32(b, 0)), "alliance": b[4], "to_japan": b[5],
                        "to_allies": b[6], "unk_7": b[7], "unk_8": b[8], "values": list(b[9:0x0E]), "flags": b[0x0E]})
            d += COUNTRY_SIZE
        return out

    # ------------------------------------------------------------ faces
    def face_raw(self, n: int) -> bytes:
        if n not in self._faces:
            self._faces[n] = koei_lz.decompress(self._lz, self.u32(FACE_POINTERS + 4 * n), len(self.data))[0]
        return self._faces[n]

    def face_palette(self, n: int) -> list[int]:
        o = FACE_PALETTES + 32 * self.u16(FACE_PAL + 2 * n)
        return [self.u16(o + 2 * k) for k in range(16)]

    def face_pixels(self, n: int) -> list[int]:
        return packed_pixels(self.face_raw(n), FACE_W, FACE_H)

    def face_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = [md_rgb(c) for c in self.face_palette(n)]
        return [pal[c] for c in self.face_pixels(n)]

    # ------------------------------------------------------------ world map
    def world_tilemap(self) -> list[int]:
        return [self.u16(WORLD_TILEMAP + 2 * i) for i in range(WORLD_W * WORLD_H)]

    def world_rgb(self) -> list[tuple[int, int, int]]:
        pal = [md_rgb(self.u16(WORLD_PALETTE + 2 * k)) for k in range(16)]
        w = WORLD_W * 8
        out = [(0, 0, 0)] * (w * WORLD_H * 8)
        for i, e in enumerate(self.world_tilemap()):
            px = packed_pixels(self.data[WORLD_TILES + 32 * ((e & 0x7FF) - WORLD_TILE0):][:32], 1, 1)
            for k, c in enumerate(px):
                y, x = k // 8, k % 8
                y, x = (7 - y if e & 0x1000 else y), (7 - x if e & 0x800 else x)
                out[(i // WORLD_W * 8 + y) * w + i % WORLD_W * 8 + x] = pal[c]
        return out
