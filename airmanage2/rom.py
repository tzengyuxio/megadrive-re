"""MD エアーマネジメントII 航空王をめざせ (KOEI, 1994): ROM decoding.

The data tables are the SFC version's (~/works/superfamicom-re/airmanage2), value for value: the same records
with big-endian words and 4-byte pointers (aircraft records padded to 12 bytes). The code is 68000 C. Text is
Shift-JIS (cp932, half-width katakana as single bytes). There is no file table: faces, palettes and maps are
reached through absolute addresses in the code. Offsets are ROM offsets (= 68000 addresses); RAM addresses are
written $FFxxxx.
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.append(os.path.join(REPO, "haouden"))
import lz  # KOEI LZ as the MD games' table-less C decoder ($3EB1A here)

DEFAULT_ROM = os.path.join(REPO, "roms", "Air Management II - Koukuuou o Mezase (Japan).zip")

# ---------------------------------------------------------------- tables (same order and values as the SFC bank $05)
CITY_COUNT = 89
BUSINESS = 0x4706E              # 15 pointers: related businesses (half-width)
CITY_NAME = 0x47410             # 89 pointers: half-width city name
CITY_WORLD_XY = 0x47574         # 89 x (x, y) bytes: city on the world map
CITY_AREA_XY = 0x47626          # 89 x (x, y) bytes: city on its area map
AIRLINE_COUNT = 32
AIRLINE = 0x476D8               # 32 pointers: default airline name of home city i (cities 0-31 can be home cities)
COUNTRY_COUNT = 57
COUNTRY = 0x47758               # 57 pointers: country name (0 = "ec", unused by the cities)
COUNTRY_E7DA = 0x4783C          # 57 bytes copied to $FF9964 at game start (unsolved; SFC $05:E7DA)
TABLE_E815 = 0x47875            # 55 bytes (unsolved; SFC $05:E815)
AREA_COUNT = 7
AREA_NAME = 0x478B0             # 7 pointers
AREA_CITIES = 0x478CC           # 7 x 4 bytes: first home city, count, first other city, count
AREA_HQ_MASK = 0x478EC          # 7 x BE32: bit i = city i is a home city of this area
AIRCRAFT_COUNT = 53
AIRCRAFT_NAME = 0x4790C         # 53 pointers
AIRCRAFT = 0x479E0              # 53 x 12 bytes, see aircraft()
AIRCRAFT_SIZE = 12
MAKER_COUNT = 12
MAKER_NAME = 0x47C5C            # 12 pointers
MAKER_EEBC = 0x47C8C            # 12 bytes (unsolved; SFC $05:EEBC; the last byte is FF here, 02 on the SFC)
MAKER_FACE = 0x47C98            # 12 x 4 bytes: face descriptor (kind BE16 = 2, image, palette)
MONTH = 0x47CD6                 # 12 pointers
CITY_STATE_A = 0x47EAA          # 89 x 4 bytes: city record at the start of scenario 1 (country, 3 values)
CITY_STATE_B = 0x4800E          # 89 x 4 bytes: the same at the start of scenario 4
CITY_SLOT_A = 0x481B2           # 89 x 2 bytes: second city record, scenario 1
CITY_SLOT_B = 0x48264           # 89 x 2 bytes: second city record, scenario 4
DIFFICULTY = 0x4831E            # 5 pointers
BUSINESS_TYPE = 0x485A0         # 5 pointers
SETUP_FACE = 0x4865A            # face descriptor of the guide on the setup screens (MAKER image 5, palette 25)
EVENTS = 0x48914                # 55 world events x 8 bytes: year BE16, quarter BE16, message, target, type, value
EVENT_COUNT = 55
# memcpy'd at game start ($9D8E): (ROM, RAM, bytes)
INIT_COPIES = [(0x4783C, 0xFF9964, 57), (0x47D06, 0xFF25B8, 192), (0x47DC6, 0xFF23F0, 228), (0x48172, 0xFF9858, 64)]

SCENARIO_COUNT = 4
# The scenario menu draws names and years as pictures (tiles 0x69FCE / 0x6AA2A …, $7E58), not strings; these are
# read off the screen (same as the SFC strings)
SCENARIOS = [("ジェット時代の幕開け", 1955), ("大量輸送時代", 1970), ("世界を覆う航路網", 1985),
             ("新世代のネットワーク", 2000)]

# RAM after the start ($9D8E)
RAM_SCENARIO = 0xFFA6F6         # word: scenario 0-3
RAM_TIME = 0xFF1FC4             # word: quarters since 1955 JAN (events with 4 x year + quarter - 7820 <= it apply)
RAM_CITY = 0xFF2050             # 89 x 4 bytes (SFC WRAM $2CBD)
RAM_CITY2 = 0xFF97A4            # 89 x 2 bytes (SFC WRAM $3E37)
RAM_PLAYER = 0xFFB2A4           # 4 x 36 bytes: +1 home city, +0x23 palette of the player's secretary and staff
RAM_PLAYER_SIZE = 36
RAM_CUR_PLAYER = 0xFF9788       # byte
RAM_SECRETARY = 0xFF22C4        # 4 x face descriptor (kind 0, image, palette)
RAM_STAFF = 0xFF1F84            # 4 players x 4 face descriptors (kind 1, image, palette byte unused)

# ---------------------------------------------------------------- faces
# 40 x 48 = 5 x 6 packed 4bpp tiles row-major (960 bytes), no headers. Drawn by $308E from a descriptor
# (kind BE16, image, palette): SECRET / STAFF take the palette from the current player's record +0x23, MAKER / MAYOR
# from the descriptor. The images are the SFC ones pixel for pixel; the 30 palettes are recoloured for the MD.
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
FACE_FILES = [(0xC2D78, 7, "SECRET", "秘書"), (0xC0438, 11, "STAFF", "職員"), (0xC47B8, 6, "MAKER", "メーカー"),
              (0xC5E38, 5, "MAYOR", "国の代表")]        # by descriptor kind
FACE_PALETTES = 0xC0078         # 30 palettes x 16 MD colours (colour 0 transparent)
FACE_PALETTE_COUNT = 30
FACE_ANIM = (0xC70F8, 0xCD000)  # eye / mouth animation tiles of the four kinds (the first frame is in the face)
# $9B34 / $9BD0: secretary and staff palette = base by the home city's area + random 0..3; $2D84C: country
# representative = (kind 3, country % 5, palette by the city's area). The SFC uses 8 for area 1 and 12 for 2 / 6,
# and palettes 0-3 for the representatives.
AREA_PAL_BASE = {0: 26, 4: 26, 5: 26, 1: 12, 2: 8, 6: 8, 3: 16}
AREA_MAYOR_PAL = AREA_PAL_BASE

# ---------------------------------------------------------------- maps (plane B from VRAM tile 1, palette line 1)
MAP_W, MAP_H = 32, 22
WORLD_PALETTE = 0x70022         # 16 MD colours
WORLD_TILEMAP = 0x70042         # 32 x 22 BE16
WORLD_TILES = 0x705C2           # KOEI LZ: 704 tiles
AREA_PALETTE = 0x72634          # 16 MD colours, all areas
AREA_TILEMAP = 0x72654          # 32 x 23 BE16 shared by the 7 areas (the game draws 22 rows and loads 704 tiles)
AREA_TILE_OFFSET = 0x72C14      # 7 BE16: word offset of each area's tiles from AREA_TILES
AREA_TILES = 0x72C22            # 7 KOEI LZ streams: 736 tiles each

MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            return z.read(z.namelist()[0])
    with open(path, "rb") as f:
        return f.read()


def decode_tile(raw: bytes) -> list[int]:
    """32 bytes packed 4bpp → 64 colour numbers."""
    return [v for b in raw for v in (b >> 4, b & 15)]


def half_to_full(s: str) -> str:
    """A half-width name in full width: katakana via NFKC, ASCII to full-width letters, long vowel as －."""
    s = unicodedata.normalize("NFKC", s).replace("ー", "－")
    return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in s)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)

    def u8(self, a: int) -> int:
        return self.data[a]

    def u16(self, a: int) -> int:
        return int.from_bytes(self.data[a:a + 2], "big")

    def u32(self, a: int) -> int:
        return int.from_bytes(self.data[a:a + 4], "big")

    def cstr(self, a: int) -> str:
        return self.data[a:self.data.index(b"\0", a)].decode("cp932")

    def strings(self, table: int, n: int) -> list[str]:
        return [self.cstr(self.u32(table + 4 * i)) for i in range(n)]

    # ------------------------------------------------------------ cities, areas, countries
    def areas(self) -> list[dict]:
        names, d = self.strings(AREA_NAME, AREA_COUNT), self.data
        o = AREA_CITIES
        return [{"index": i, "name": names[i], "hq_first": d[o + 4 * i], "hq_count": d[o + 4 * i + 1],
                 "other_first": d[o + 4 * i + 2], "other_count": d[o + 4 * i + 3],
                 "hq_mask": self.u32(AREA_HQ_MASK + 4 * i)} for i in range(AREA_COUNT)]

    def city_area(self, city: int) -> int:
        """$AE98: the area whose home-city range (cities < 32) or other-city range holds the city."""
        for a in self.areas():
            first, count = (a["hq_first"], a["hq_count"]) if city < 32 else (a["other_first"], a["other_count"])
            if first <= city < first + count:
                return a["index"]
        raise ValueError(city)

    def countries(self) -> list[dict]:
        names = self.strings(COUNTRY, COUNTRY_COUNT)
        return [{"index": i, "name": names[i], "e7da": self.data[COUNTRY_E7DA + i]} for i in range(COUNTRY_COUNT)]

    def cities(self) -> list[dict]:
        d = self.data
        names, airlines = self.strings(CITY_NAME, CITY_COUNT), self.strings(AIRLINE, AIRLINE_COUNT)
        countries = self.strings(COUNTRY, COUNTRY_COUNT)
        out = []
        for i in range(CITY_COUNT):
            country = d[CITY_STATE_A + 4 * i]
            out.append({"index": i, "name": names[i], "name_full": half_to_full(names[i]), "area": self.city_area(i),
                        "country": country, "country_name": countries[country], "home": i < 32,
                        "airline": airlines[i] if i < 32 else "",
                        "world_x": d[CITY_WORLD_XY + 2 * i], "world_y": d[CITY_WORLD_XY + 2 * i + 1],
                        "area_x": d[CITY_AREA_XY + 2 * i], "area_y": d[CITY_AREA_XY + 2 * i + 1]})
        return out

    # ------------------------------------------------------------ scenarios, events
    def events(self) -> list[dict]:
        """World events: type 0 = byte 0 (country) of city `target`'s record becomes `value`; type 1 = byte
        `target` of the country table $FF9964 becomes `value` (meaning unsolved). message 255 = shown with the
        event before it. $A9A2 applies those dated up to the start ($29B86)."""
        out = []
        for i in range(EVENT_COUNT):
            e = self.data[EVENTS + 8 * i:EVENTS + 8 * i + 8]
            out.append({"index": i, "year": e[0] << 8 | e[1], "quarter": e[2] << 8 | e[3], "message": e[4],
                        "target": e[5], "type": e[6], "value": e[7]})
        return out

    @staticmethod
    def start_time(scenario: int) -> int:
        """$FF1FC4 at the start: quarters since 1955 JAN (the game starts in APR)."""
        return 4 * (SCENARIOS[scenario][1] - 1955) + 1

    def _started(self, scenario: int) -> list[dict]:
        return [e for e in self.events() if 4 * e["year"] + e["quarter"] - 7820 <= self.start_time(scenario)]

    def scenario_cities(self, scenario: int) -> tuple[bytes, bytes]:
        """$FF2050 (89 x 4) and $FF97A4 (89 x 2) as $9D8E fills them: scenario 0 / 3 copy table A / B, 1 and 2
        take byte 0 from B and interpolate bytes 1-3 and byte 0 of the second record ($9F6E):
        a + trunc((b - a) * scenario / 3), clamped to 0..255; then the type-0 events up to the start."""
        d = self.data
        if scenario in (0, 3):
            t4, t2 = (CITY_STATE_A, CITY_SLOT_A) if scenario == 0 else (CITY_STATE_B, CITY_SLOT_B)
            rec, rec2 = bytearray(d[t4:t4 + 4 * CITY_COUNT]), d[t2:t2 + 2 * CITY_COUNT]
        else:
            def mix(a: int, b: int) -> int:
                return max(0, min(255, a + int((b - a) * scenario / 3)))

            rec, rec2 = bytearray(), bytearray()
            for i in range(CITY_COUNT):
                a, b = CITY_STATE_A + 4 * i, CITY_STATE_B + 4 * i
                rec.append(d[b])
                rec.extend(mix(d[a + k], d[b + k]) for k in (1, 2, 3))
                rec2.extend((mix(d[CITY_SLOT_A + 2 * i], d[CITY_SLOT_B + 2 * i]), 0))
        for e in self._started(scenario):
            if e["type"] == 0:
                rec[4 * e["target"]] = e["value"]
        return bytes(rec), bytes(rec2)

    def init_tables(self, scenario: int = 0) -> dict[int, bytes]:
        """{RAM address: bytes} of the tables memcpy'd at game start, the country table with the type-1 events."""
        out = {dst: bytearray(self.data[src:src + n]) for src, dst, n in INIT_COPIES}
        for e in self._started(scenario):
            if e["type"] == 1:
                out[0xFF9964][e["target"]] = e["value"]
        return {a: bytes(b) for a, b in out.items()}

    # ------------------------------------------------------------ aircraft, makers
    def makers(self) -> list[dict]:
        names = self.strings(MAKER_NAME, MAKER_COUNT)
        f = MAKER_FACE
        return [{"index": i, "name": names[i], "eebc": self.data[MAKER_EEBC + i], "face_kind": self.u16(f + 4 * i),
                 "face_image": self.data[f + 4 * i + 2], "face_palette": self.data[f + 4 * i + 3]}
                for i in range(MAKER_COUNT)]

    def aircraft(self) -> list[dict]:
        """12-byte records: maker, seats / 10, range km BE16, base price (万$) BE16, first year - 1900,
        last year - 1900 (200 = still built), 100 - fuel economy, 100 - maintainability, flags (unsolved), 0."""
        names = self.strings(AIRCRAFT_NAME, AIRCRAFT_COUNT)
        out = []
        for i in range(AIRCRAFT_COUNT):
            r = self.data[AIRCRAFT + AIRCRAFT_SIZE * i:AIRCRAFT + AIRCRAFT_SIZE * (i + 1)]
            out.append({"index": i, "name": names[i], "maker": r[0], "seats": r[1] * 10, "range_km": r[2] << 8 | r[3],
                        "price": r[4] << 8 | r[5], "first_year": 1900 + r[6],
                        "last_year": None if r[7] == 200 else 1900 + r[7], "fuel": 100 - r[8],
                        "maintenance": 100 - r[9], "flags": r[10], "pad": r[11]})
        return out

    # ------------------------------------------------------------ faces
    def face_raw(self, kind: int, image: int) -> bytes:
        a = FACE_FILES[kind][0] + FACE_BYTES * image
        return self.data[a:a + FACE_BYTES]

    def face_pixels(self, kind: int, image: int) -> list[list[int]]:
        raw = self.face_raw(kind, image)
        out = [[0] * (FACE_W * 8) for _ in range(FACE_H * 8)]
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(raw[32 * t:32 * t + 32])):
                out[t // FACE_W * 8 + i // 8][t % FACE_W * 8 + i % 8] = v
        return out

    def face_palette(self, p: int) -> list[int]:
        return [self.u16(FACE_PALETTES + 32 * p + 2 * i) for i in range(16)]

    def face_rgb(self, kind: int, image: int, palette: int) -> list[list[tuple[int, int, int]]]:
        pal = [md_rgb(c) for c in self.face_palette(palette)]
        return [[pal[v] for v in row] for row in self.face_pixels(kind, image)]

    def secretary_palettes(self, home_city: int) -> list[int]:
        """The 4 palettes a player's secretary / staff can get ($9B34)."""
        base = AREA_PAL_BASE[self.city_area(home_city)]
        return list(range(base, base + 4))

    def mayor_face(self, city: int, country: int | None = None) -> tuple[int, int, int]:
        """$2D84C: (kind 3, country % 5, palette by the city's area); country = byte 0 of the city record."""
        if country is None:
            country = self.data[CITY_STATE_A + 4 * city]
        return 3, country % 5, AREA_MAYOR_PAL[self.city_area(city)]

    def faces(self) -> list[dict]:
        """Portrait list for the exports: each SECRET / STAFF / MAYOR image once with the European palette (26),
        then the 12 maker descriptors."""
        out = [{"kind": k, "file": FACE_FILES[k][2], "label": FACE_FILES[k][3], "image": i, "palette": 26}
               for k in (0, 1, 3) for i in range(FACE_FILES[k][1])]
        for m in self.makers():
            out.append({"kind": m["face_kind"], "file": "MAKER", "label": FACE_FILES[2][3], "image": m["face_image"],
                        "palette": m["face_palette"], "maker": m["index"], "maker_name": m["name"]})
        return out

    # ------------------------------------------------------------ maps
    def _map(self, pal_a: int, tm_a: int, tiles: bytes, rows: int = MAP_H) -> list[list[tuple[int, int, int]]]:
        pal = [md_rgb(self.u16(pal_a + 2 * i)) for i in range(16)]
        img = [[(0, 0, 0)] * (8 * MAP_W) for _ in range(8 * rows)]
        for i in range(MAP_W * rows):
            e = self.u16(tm_a + 2 * i)
            t = (e & 0x7FF) - 1       # VRAM tile 1 = first tile of the stream
            px = decode_tile(tiles[32 * t:32 * t + 32])
            for j, v in enumerate(px):
                x, y = j % 8, j // 8
                img[i // MAP_W * 8 + (7 - y if e & 0x1000 else y)][i % MAP_W * 8 + (7 - x if e & 0x800 else x)] = pal[v]
        return img

    def world_tiles(self) -> bytes:
        return lz.decompress(self.data, WORLD_TILES)[0]

    def area_tiles(self, area: int) -> bytes:
        return lz.decompress(self.data, AREA_TILES + 2 * self.u16(AREA_TILE_OFFSET + 2 * area))[0]

    def world_map(self) -> list[list[tuple[int, int, int]]]:
        """256 x 176 world map (start of the game, route screens)."""
        return self._map(WORLD_PALETTE, WORLD_TILEMAP, self.world_tiles())

    def area_map(self, area: int, rows: int = MAP_H) -> list[list[tuple[int, int, int]]]:
        """256 x 176 area map (main screen, home city selection); rows=23 adds the row the game doesn't draw."""
        return self._map(AREA_PALETTE, AREA_TILEMAP, self.area_tiles(area), rows)
