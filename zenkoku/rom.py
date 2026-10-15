"""MD 信長の野望・全国版 / Nobunaga's Ambition (KOEI, 1993) ROM decoding.

Offsets are ROM offsets (= 68000 addresses); RAM addresses are offsets in $FF0000-$FFFFFF. See
docs/ROM_FORMAT.md. The data is the SFC version's (~/works/superfamicom-re/zenkoku) stored big-endian, the text
is Shift-JIS (Japan) or ASCII (USA), and the compressed graphics use the KOEI LZ format of tools/koei_lz.py (the
MD decoder at $4BAC has no lookup tables, so the SFC table block is appended to the ROM image for decoding).
The two versions run the same program with different addresses (LAYOUTS); the USA one keeps one 11-byte name per
daimyo instead of a surname and a given name table.
"""
import os
import sys
import unicodedata
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz
from triage import load_rom

DEFAULT_ROM = os.path.join(REPO, "roms", "Nobunaga no Yabou - Zenkoku Ban (Japan).zip")
USA_ROM = os.path.join(REPO, "roms", "Nobunaga's Ambition (USA).zip")

SCENARIO_COUNT = 4
SCENARIO1_YEAR, SCENARIO1_DAIMYO = 1560, 17  # set by the loader's code, not a table
DAIMYO_SLOTS = 53                        # 0-49: daimyo of province k at the start, 50-52 明智 羽柴 柴田
DAIMYO_RAM, DAIMYO_SIZE = 0x0F80, 8      # age, 健康, 野心, 運, 魅力, 知力, word person (face) id
DAIMYO_STATS = [("Health", "健康"), ("Ambition", "野心"), ("Luck", "運"), ("Charm", "魅力"), ("IQ", "知力")]
UNK_RAM = 0x1130                         # 50 bytes, unknown (mostly 1)
OWNERS_RAM = 0x1162                      # province -> owner daimyo slot (51)
PROVINCE_SIZE = 26
# Province record: 13 words, the SFC / FC order; the last one is not on any screen.
PROVINCE_FIELDS = [("Gold", "金"), ("Debt", "借金"), ("Town", "町"), ("Rice", "兵糧"), ("Kokudaka", "石高"),
                   ("Flood", "治水"), ("Loyalty", "民忠"), ("Wealth", "民財"), ("Soldiers", "兵力"),
                   ("Soldier_Loyalty", "兵忠"), ("Training", "訓練"), ("Arms", "武装"), ("Unk24", "")]
YEAR_RAM = 0x0002                        # word: start year - 1
PROVINCE_COUNT_RAM = 0x0D9E              # byte: 0x11 or 0x32
ADJ_SIZE = 8                             # neighbours, FF-terminated, zero-padded
BLOCK_0000 = 0xF7F

# 40x48 portraits, KOEI LZ streams of 960 bytes (30 tiles): 0-67 the person ids of the daimyo records, 68-72 women
# (姫). The game loads the tiles to VRAM $4000 and lays them out on plane A as a 4x4 block, a 4x2 block, a 1x4 and a
# 1x2 column, each column-major (FACE_LAYOUT), with palette line 2.
PORTRAIT_COUNT, PERSON_COUNT = 73, 68
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
FACE_LAYOUT = ([(k // 4, k % 4) for k in range(16)] + [(k // 2, 4 + k % 2) for k in range(8)]
               + [(4, k) for k in range(4)] + [(4, 4 + k) for k in range(2)])  # tile k -> (column, row)
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values

# Strategy map: a 30 x 20 tile bitmap (packed 4bpp, KOEI LZ; map_pointers[0] = 17 provinces, [1] = 50), the SFC
# picture. Unpainted land is colour 7; at the start the game paints every province from a seed point (4-connected
# fill of the seed's colour) with the 8 x 8 pattern of its owner (patterns + 32 x pattern number of the owner).
# Pattern 81 is plain colour 7. Palette line 3.
MAP_W, MAP_H = 30, 20
MAP_INDEX = {17: 0, 50: 1}
PATTERN_COUNT = 82

# Battle maps: 50 maps x 11 columns x 5 rows of terrain bytes, the SFC / FC table.
BATTLE_COUNT, BATTLE_W, BATTLE_H = 50, 11, 5
TERRAIN = {0x02: ("none", "場外"), 0x04: ("plain", "平地"), 0x08: ("town", "町"), 0x10: ("forest", "林"),
           0x20: ("castle", "城"), 0x40: ("water", "川・海"), 0x80: ("mountain", "山")}


@dataclass(frozen=True)
class Layout:
    region: str
    serial: bytes                        # header 0x180
    # scenario loader: (provinces, block at $0000, block 2) per scenario; block 2 RAM address and size
    scenarios: tuple
    block2_ram: int
    block2_size: int
    # per-scenario tables: RAM address -> (size, ROM of scenario 1, base of scenarios 2-4, stride)
    tables: dict
    names: tuple                         # ((RAM, size) of each name part): surname + given / one name
    provinces_ram: int
    pattern_ram: int
    province_names_ram: int
    province_name_size: int
    adj_ram: int
    regions_ram: int
    years: int                           # word per scenario, index 1-3
    daimyo_counts: int                   # word per scenario, index 1-3
    daimyo_count_ram: int
    loader_done: int                     # where both loader branches meet
    menu: int                            # scenario menu strings
    mode17_province: int                 # 17 bytes: 17-mode province -> 50-mode province (battle map)
    face_pointers: int
    face_palette: int
    map_pointers: int
    patterns: int
    map_seed_x: dict                     # word per province, minus 8 = bitmap pixel
    map_seed_y: dict
    map_palette: int
    battle_maps: int


LAYOUTS = {
    "J": Layout(
        region="J", serial=b"GM T-76133",
        scenarios=((17, 0x29AB2, 0x29408), (50, 0x25EB2, 0x2904C), (50, 0x25EB2, 0x2904C), (50, 0x25EB2, 0x2904C)),
        block2_ram=0x1978, block2_size=0x3BA,
        tables={
            0x0F80: (0x1A8, 0x27BF4, 0x26C8E, 0x1B0),   # daimyo: 53 x 8 (records of 54 slots in ROM)
            0x1130: (0x032, 0x2AA32, 0x27A92, 0x032),
            0x1162: (0x033, 0x2AA64, 0x27B27, 0x033),
            0x1196: (0x173, 0x2AA98, 0x271DB, 0x173),   # surnames: 53 x 7
            0x130A: (0x109, 0x2AC0C, 0x2769F, 0x109),   # given names: 53 x 5
            0x1414: (0x52E, 0x2AD16, 0x27876, 0x52E),   # provinces: 51 x 26
            0x1942: (0x035, 0x2B244, 0x28CF9, 0x035),   # daimyo -> strategy map pattern (53)
        },
        names=((0x1196, 7), (0x130A, 5)), provinces_ram=0x1414, pattern_ram=0x1942,
        province_names_ram=0x19AE, province_name_size=9, adj_ram=0x1B70, regions_ram=0x1D00,
        years=0x26E30, daimyo_counts=0x26E36, daimyo_count_ram=0xD3DC, loader_done=0x9152, menu=0x22A56,
        mode17_province=0x25C10, face_pointers=0x51F74, face_palette=0x2B6EC, map_pointers=0x461C6,
        patterns=0x461CE, map_seed_x={50: 0x2F3C0, 17: 0x2F424}, map_seed_y={50: 0x2F446, 17: 0x2F4AA},
        map_palette=0x2B6AC, battle_maps=0x2BC28),
    "U": Layout(
        region="U", serial=b"GM T-76076",
        scenarios=((17, 0x2B616, 0x2AF08), (50, 0x27966, 0x2AB1A), (50, 0x27966, 0x2AB1A), (50, 0x27966, 0x2AB1A)),
        block2_ram=0x1942, block2_size=0x3EC,
        tables={
            0x0F80: (0x1A8, 0x29608, 0x28742, 0x1B0),
            0x1130: (0x032, 0x2C596, 0x294A6, 0x032),
            0x1162: (0x033, 0x2C5C8, 0x2953B, 0x033),
            0x1196: (0x247, 0x2C5FC, 0x28BBB, 0x247),   # names: 53 x 11
            0x13DE: (0x52E, 0x2C844, 0x2928A, 0x52E),
            0x190C: (0x035, 0x2CD72, 0x2A70D, 0x035),
        },
        names=((0x1196, 11),), provinces_ram=0x13DE, pattern_ram=0x190C,
        province_names_ram=0x1978, province_name_size=10, adj_ram=0x1B6C, regions_ram=0x1CFC,
        years=0x288E4, daimyo_counts=0x288EA, daimyo_count_ram=0xD3E0, loader_done=0x9468, menu=0x2421E,
        mode17_province=0x2769C, face_pointers=0x5048C, face_palette=0x2D452, map_pointers=0x446DE,
        patterns=0x446E6, map_seed_x={50: 0x31458, 17: 0x314BC}, map_seed_y={50: 0x314DE, 17: 0x31542},
        map_palette=0x2D412, battle_maps=0x2D990),
}

# Shift-JIS; half-width kana are shown as hiragana. EB9F EBA0 EBA1 draw 長宗我部 in three glyphs.
LIGATURES = {b"\xeb\x9f\xeb\xa0\xeb\xa1": "長宗我部"}


def be16(raw: bytes, i: int) -> int:
    return raw[i] << 8 | raw[i + 1]


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


def pixel(bm: bytes, width: int, x: int, y: int) -> int:
    """Colour of pixel (x, y) of a bitmap of packed 4bpp tiles, width tiles per row."""
    b = bm[((y >> 3) * width + (x >> 3)) * 32 + (y & 7) * 4 + (x & 7) // 2]
    return b >> 4 if x % 2 == 0 else b & 15


def flood_fill(bm: bytearray, width: int, height: int, x: int, y: int, pattern: bytes) -> int:
    """Paint the 4-connected area of pixel (x, y)'s colour with an 8 x 8 packed pattern; returns the pixel count."""
    w, h = width * 8, height * 8
    if not (0 <= x < w and 0 <= y < h):
        return 0
    target = pixel(bm, width, x, y)
    seen = {(x, y)}
    stack = [(x, y)]
    while stack:
        px, py = stack.pop()
        for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and pixel(bm, width, nx, ny) == target:
                seen.add((nx, ny))
                stack.append((nx, ny))
    for px, py in seen:
        o = ((py >> 3) * width + (px >> 3)) * 32 + (py & 7) * 4 + (px & 7) // 2
        c = pattern[(py & 7) * 4 + (px & 7) // 2]
        bm[o] = (bm[o] & 0x0F) | (c & 0xF0) if px % 2 == 0 else (bm[o] & 0xF0) | (c & 0x0F)
    return len(seen)


def text(raw: bytes) -> str:
    """Shift-JIS / ASCII bytes up to 00 → str (half-width kana as hiragana, the 長宗我部 glyphs as one word)."""
    raw = raw.split(b"\0", 1)[0]
    out, i = [], 0
    while i < len(raw):
        for seq, s in LIGATURES.items():
            if raw.startswith(seq, i):
                out.append(s)
                i += len(seq)
                break
        else:
            n = 2 if 0x81 <= raw[i] < 0xA0 or 0xE0 <= raw[i] < 0xFD else 1
            ch = unicodedata.normalize("NFKC", raw[i:i + n].decode("cp932", errors="replace"))
            out.append("".join(chr(ord(k) - 0x60) if "ァ" <= k <= "ン" and n == 1 else k for k in ch))
            i += n
    return "".join(out)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom(path)
        self.L = next(lay for lay in LAYOUTS.values() if self.data[0x180:0x180 + len(lay.serial)] == lay.serial)
        self._lz = self.data + koei_lz.BLOCK  # the decoder's tables, which the MD ROM doesn't have

    def u16(self, o: int) -> int:
        return be16(self.data, o)

    def u32(self, o: int) -> int:
        return int.from_bytes(self.data[o:o + 4], "big")

    def lz(self, p: int) -> bytes:
        return koei_lz.decompress(self._lz, p, len(self.data))[0]

    # ------------------------------------------------------------ scenarios
    def scenario_titles(self) -> list[str]:
        """'title (year)' of the 4 scenarios, from the menu strings (Japan: 'n:title (year)'; USA: '(year)' as its
        own string right before 'n:title')."""
        parts = [p.lstrip(b"\0\xff") for p in self.data[self.L.menu:self.L.menu + 0x100].split(b"\0")]
        out = {}
        for k, part in enumerate(parts):
            if len(part) > 2 and part[1:2] == b":" and part[:1] in b"1234":
                t = text(part[2:])
                if "(" not in t:
                    t += " " + text(parts[k - 1])
                out[int(part[:1])] = t
        return [out[k] for k in sorted(out)]

    def scenario_sources(self, s: int) -> list[tuple[int, int, int]]:
        """[(RAM address, ROM offset, size)] of what the loader copies for scenario s (0-3), in its order."""
        _, b0000, b2 = self.L.scenarios[s]
        out = [(0x0000, b0000, BLOCK_0000), (self.L.block2_ram, b2, self.L.block2_size)]
        for addr, (size, rom1, base, stride) in self.L.tables.items():
            out.append((addr, rom1 if s == 0 else base + stride * s, size))
        return out

    def ram_end(self) -> int:
        return self.L.block2_ram + self.L.block2_size

    def scenario_image(self, s: int) -> bytes:
        """RAM $FF0000 up to the end of block 2 right after the loader ran."""
        img = bytearray(self.ram_end())
        for addr, o, size in self.scenario_sources(s):
            img[addr:addr + size] = self.data[o:o + size]
        img[YEAR_RAM:YEAR_RAM + 2] = (self.scenario_year(s) - 1).to_bytes(2, "big")
        return bytes(img)

    def scenario_year(self, s: int) -> int:
        return SCENARIO1_YEAR if s == 0 else self.u16(self.L.years + 2 * s)

    def scenario_daimyo_count(self, s: int) -> int:
        return SCENARIO1_DAIMYO if s == 0 else self.u16(self.L.daimyo_counts + 2 * s)

    def province_count(self, s: int) -> int:
        return self.L.scenarios[s][0]

    def province_names(self, s: int) -> list[str]:
        img, a, n = self.scenario_image(s), self.L.province_names_ram, self.L.province_name_size
        return [text(img[a + n * p:a + n * p + n]) for p in range(self.province_count(s))]

    def neighbours(self, s: int) -> list[list[int]]:
        img = self.scenario_image(s)
        out = []
        for p in range(self.province_count(s)):
            raw = img[self.L.adj_ram + ADJ_SIZE * p:][:ADJ_SIZE]
            out.append(list(raw[:raw.index(0xFF)]))
        return out

    def daimyos(self, s: int) -> list[dict]:
        """The 53 daimyo slots of scenario s; empty slots (all zero) are left out. 'surname' and 'given' are empty
        in the USA version, which has one name per daimyo."""
        img = self.scenario_image(s)
        owners = img[OWNERS_RAM:OWNERS_RAM + 51]
        out = []
        for d in range(DAIMYO_SLOTS):
            rec = img[DAIMYO_RAM + DAIMYO_SIZE * d:][:DAIMYO_SIZE]
            parts = [text(img[a + n * d:a + n * d + n]) for a, n in self.L.names]
            if not any(rec) and not any(parts):
                continue
            surname, given = parts if len(parts) == 2 else ("", "")
            out.append({
                "index": d, "surname": surname, "given": given, "name": "".join(parts), "age": rec[0],
                **{k: rec[1 + i] for i, (k, _) in enumerate(DAIMYO_STATS)},
                "person": be16(rec, 6), "pattern": img[self.L.pattern_ram + d],
                "provinces": [p for p in range(self.province_count(s)) if owners[p] == d],
            })
        return out

    def provinces(self, s: int) -> list[dict]:
        img = self.scenario_image(s)
        names = self.province_names(s)
        nbr = self.neighbours(s)
        out = []
        for p in range(self.province_count(s)):
            rec = img[self.L.provinces_ram + PROVINCE_SIZE * p:][:PROVINCE_SIZE]
            out.append({
                "index": p, "name": names[p], "owner": img[OWNERS_RAM + p], "region": img[self.L.regions_ram + p],
                "neighbours": nbr[p], "unk1130": img[UNK_RAM + p],
                **{k: be16(rec, 2 * i) for i, (k, _) in enumerate(PROVINCE_FIELDS)},
            })
        return out

    def mode17_province(self) -> list[int]:
        return list(self.data[self.L.mode17_province:self.L.mode17_province + 17])

    def persons(self) -> list[dict]:
        """Every person id with the name and the scenarios (1-4) that use it, in id order."""
        seen: dict[int, dict] = {}
        for s in range(SCENARIO_COUNT):
            for d in self.daimyos(s):
                p = seen.setdefault(d["person"], {"id": d["person"], "name": d["name"], "surname": d["surname"],
                                                  "given": d["given"], "scenarios": []})
                assert p["name"] == d["name"], (p, d)
                p["scenarios"].append(s + 1)
        return [seen[k] for k in sorted(seen)]

    # ------------------------------------------------------------ faces
    def face_offset(self, n: int) -> int:
        return self.u32(self.L.face_pointers + 4 * n)

    def face_raw(self, n: int) -> bytes:
        """960 bytes (30 4bpp tiles, in VRAM order) of portrait n (0-72)."""
        raw = self.lz(self.face_offset(n))
        assert len(raw) == FACE_BYTES
        return raw

    def face_pixels(self, n: int) -> bytes:
        """Portrait n → 40x48 colour numbers 0-15, laid out as on screen."""
        raw = self.face_raw(n)
        px = bytearray(40 * 48)
        for t, (cx, cy) in enumerate(FACE_LAYOUT):
            for y in range(8):
                for x in range(8):
                    b = raw[32 * t + 4 * y + x // 2]
                    px[(cy * 8 + y) * 40 + cx * 8 + x] = b >> 4 if x % 2 == 0 else b & 15
        return bytes(px)

    def palette(self, o: int) -> list[tuple[int, int, int]]:
        return [md_rgb(self.u16(o + 2 * i)) for i in range(16)]

    def face_palette(self) -> list[tuple[int, int, int]]:
        return self.palette(self.L.face_palette)

    def face_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = self.face_palette()
        return [pal[v] for v in self.face_pixels(n)]

    # ------------------------------------------------------------ strategy map
    def map_seeds(self, mode: int) -> list[tuple[int, int]]:
        xs, ys = self.L.map_seed_x[mode], self.L.map_seed_y[mode]
        return [(self.u16(xs + 2 * p) - 8, self.u16(ys + 2 * p) - 8) for p in range(mode)]

    def pattern(self, k: int) -> bytes:
        return self.data[self.L.patterns + 32 * k:self.L.patterns + 32 * k + 32]

    def map_bitmap(self, s: int | None = None, mode: int = 50) -> bytes:
        """The map's 600 tiles (4bpp, row-major) as the game shows them at the start of scenario s (provinces
        painted with their owners' patterns), or unpainted if s is None."""
        if s is not None:
            mode = self.province_count(s)
        bm = bytearray(self.lz(self.u32(self.L.map_pointers + 4 * MAP_INDEX[mode])))
        if s is not None:
            img = self.scenario_image(s)
            for p, (x, y) in enumerate(self.map_seeds(mode)):
                flood_fill(bm, MAP_W, MAP_H, x, y, self.pattern(img[self.L.pattern_ram + img[OWNERS_RAM + p]]))
        return bytes(bm)

    def map_rgb(self, s: int | None = None, mode: int = 50) -> tuple[int, int, list]:
        bm = self.map_bitmap(s, mode)
        pal = self.palette(self.L.map_palette)
        w, h = MAP_W * 8, MAP_H * 8
        return w, h, [pal[pixel(bm, MAP_W, x, y)] for y in range(h) for x in range(w)]

    # ------------------------------------------------------------ battle maps
    def battle_cells(self, m: int) -> bytes:
        o = self.L.battle_maps + m * BATTLE_W * BATTLE_H
        return self.data[o:o + BATTLE_W * BATTLE_H]
