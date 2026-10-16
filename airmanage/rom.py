"""MD エアーマネジメント 大空に賭ける (KOEI, 1992): ROM decoding.

The data tables are the SFC version's (~/works/superfamicom-re/airmanage), value for value, as big-endian words
with 4-byte pointers; the code is 68000 C. Text is Shift-JIS (cp932, half-width katakana as single bytes).
"Files" (faces, palettes, the world map) are a BE16 byte size followed by the data. Offsets are ROM offsets
(= 68000 addresses); RAM addresses are written $FFxxxx.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROMS = os.path.join(os.path.dirname(HERE), "roms")
DEFAULT_ROM = os.path.join(ROMS, "Air Management - Oozora ni Kakeru (Japan).zip")

CITY_COUNT = 22
DIFFICULTY = 0x5F364            # 5 pointers: - pro - … beginner
DISTANCE = 0x5F378              # 22 x 22 BE16, km / 10, diagonal FFFF; row = from, column = to
MATRIX2 = 0x5F740               # 22 x 22 BE16, symmetric, diagonal 0 (unsolved, as in the SFC version)
CITY_TYPE = 0x5FB08             # 22 BE16: 0 ミリオン 1 ビジネス 2 リゾ－ト 3 バランス
CITY_KANA = 0x5FB34             # 22 pointers: half-width city name
CITY_NAME = 0x5FB8C             # 22 pointers: full-width city name
AIRLINE = 0x5FBE4               # 22 pointers: default airline name per home city
AIRPORT = 0x5FC3C               # 22 pointers: airport name
CITY_XY = 0x5FC94               # 22 x (x, y) BE16: city on the world map (HQ cursor $FF129C starts at 東京)
MONTHS = 0x5FCEC                # 12 pointers: jan … dec
MAKER_COLOR = 0x5FD1C           # 5 MD colours: the makers' colours (SFC BGR555 converted; the 5th is the SFC word as is)
AIRCRAFT = 0x5FD26              # 20 x 18 bytes, see aircraft()
AIRCRAFT_COUNT = 20
AIRCRAFT_SIZE = 18
MAKER_FACE = 0x5FE8E            # 5 x 4 bytes: face descriptor (kind BE16, image, palette)
CITY_ROUTES = 0x5FEA2           # 22 x 3 x (city BE16, byte, byte) (guess: start routes; bytes unsolved)
MAKER_NAME = 0x5FFAA            # 5 pointers
AIRLINE2 = 0x5FFBE              # 22 pointers: second airline name (unsolved, lower-case prefixes as in SFC)
AIRCRAFT_GFX = 0x60016          # 20 x (side picture BE16, top picture BE16 or FFFF) (unverified)
AIRCRAFT_ASCII = 0x60084        # 26 pointers: 20 lower-case model names, then 6 rank strings "     " … "*****"
WORLD_XY = 0x600EC              # 22 x (x, y) BE16 (unsolved: a larger world coordinate)
MAKER_AIRCRAFT = [(0, 6), (6, 5), (11, 4), (15, 4), (0, 0)]  # (first, count), as in the SFC trade screen

SCENARIO_CITY = 0xE6BA8         # 2 scenarios x 22 cities x 5 BE16: pop / 100 (万人), 観光地, 経済力, slots, HQ slots
SCENARIO_HQ = 0xE6D60           # 22 x 4 BE16 (unsolved, SFC: player record +18..+25)
SCENARIO_FUNDS = 0xE6E10        # 2 scenarios x 22 BE32 (guess: starting funds, 万$, by home city)
SCENARIOS = [("シナリオ1", 1963), ("シナリオ2", 1983)]

# RAM after the start (verify_scenarios.py)
RAM_SCENARIO = 0xFF1D9E         # both scenarios' 22 x 5 words, copied from SCENARIO_CITY
RAM_CITY = 0xFF1054             # 22 x 12 bytes: +2 pop, +4 観光地, +6 経済力, +10 (2 x 観光地 + 経済力) / 3
RAM_CITY_SIZE = 12
RAM_SLOT = 0xFFA740             # 22 x 20 bytes: +2 slots, +3 used, +4 + 2p player p's slots (bytes)
RAM_SLOT_SIZE = 20
RAM_PLAYER = 0xFFB084           # 4 x 0x42 bytes: +2 home city
RAM_PLAYER_SIZE = 0x42
RAM_MANAGER = 0xFF3490          # 4 x face descriptor: the players' aides
RAM_PERSON = 0xFF2E64           # 4 x 3 x face descriptor: the players' negotiation partners

# Faces: 40 x 48, 5 x 6 packed 4bpp tiles, row-major (960 bytes). The drawing function $3BE4 takes a
# descriptor (kind BE16, image byte, palette byte) and picks the file by kind.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
FACE_FILES = [(0x69564, 8, "MANAGER", "部下"), (0x6B366, 20, "PERSON", "交渉相手"), (0x6FE68, 5, "MAKER", "メーカー")]
FACE_PALETTES = 0x755D4         # file: 5 palettes x 16 MD colours (CRAM line 3 when drawn)
FACE_PALETTE_COUNT = 5
# The game's pairing (code $88A2 for the aides, $8976 for the partners, MAKER_FACE for the makers)
MANAGER_PALETTE = [0, 1, 1, 2, 2, 3, 4, 4]

WORLD_MAP = 0x5842A             # file: palette (16), tilemap 32 x 16 (BE16, tile + palette 1), 512 tiles
MAP_W, MAP_H = 32, 16
MAP_ROW = 7                     # the HQ-selection screen draws the tilemap at plane B row 7, tiles from VRAM 0x180
MAP_TILE_BASE = 0x180
MAP_TILES = 512
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values

CITY_TYPE_NAMES = ["ミリオン", "ビジネス", "リゾ－ト", "バランス"]


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

    def words(self, a: int, n: int) -> list[int]:
        return [self.u16(a + 2 * i) for i in range(n)]

    def cstr(self, a: int) -> str:
        end = self.data.index(b"\0", a)
        return self.data[a:end].decode("cp932")

    def strings(self, table: int, n: int) -> list[str]:
        return [self.cstr(self.u32(table + 4 * i)) for i in range(n)]

    def file(self, a: int) -> bytes:
        """A data file: BE16 size, then the bytes."""
        return self.data[a + 2:a + 2 + self.u16(a)]

    # ------------------------------------------------------------ cities, scenarios

    def cities(self) -> list[dict]:
        names, kana = self.strings(CITY_NAME, CITY_COUNT), self.strings(CITY_KANA, CITY_COUNT)
        airlines, airports = self.strings(AIRLINE, CITY_COUNT), self.strings(AIRPORT, CITY_COUNT)
        airlines2 = self.strings(AIRLINE2, CITY_COUNT)
        out = []
        for c in range(CITY_COUNT):
            routes = [(self.u16(CITY_ROUTES + 12 * c + 4 * k), self.u8(CITY_ROUTES + 12 * c + 4 * k + 2),
                       self.u8(CITY_ROUTES + 12 * c + 4 * k + 3)) for k in range(3)]
            out.append({"index": c, "name": names[c], "kana": kana[c], "airport": airports[c],
                        "airline": airlines[c], "airline2": airlines2[c], "type": self.u16(CITY_TYPE + 2 * c),
                        "x": self.u16(CITY_XY + 4 * c), "y": self.u16(CITY_XY + 4 * c + 2),
                        "world_x": self.u16(WORLD_XY + 4 * c), "world_y": self.u16(WORLD_XY + 4 * c + 2),
                        "routes": routes})
        return out

    def distances(self) -> list[list[int | None]]:
        """km; None on the diagonal."""
        w = self.words(DISTANCE, CITY_COUNT * CITY_COUNT)
        return [[None if v == 0xFFFF else v * 10 for v in w[r * CITY_COUNT:(r + 1) * CITY_COUNT]]
                for r in range(CITY_COUNT)]

    def matrix2(self) -> list[list[int]]:
        w = self.words(MATRIX2, CITY_COUNT * CITY_COUNT)
        return [w[r * CITY_COUNT:(r + 1) * CITY_COUNT] for r in range(CITY_COUNT)]

    def scenario_words(self, s: int) -> list[int]:
        """The 22 x 5 words of scenario s as the game copies them to RAM_SCENARIO."""
        return self.words(SCENARIO_CITY + 220 * s, CITY_COUNT * 5)

    def scenario_cities(self, s: int) -> list[dict]:
        w = self.scenario_words(s)
        out = []
        for c in range(CITY_COUNT):
            pop, tourism, economy, slots, hq_slots = w[5 * c:5 * c + 5]
            out.append({"index": c, "population": pop * 100, "tourism": tourism, "economy": economy,
                        "slots": slots, "hq_slots": hq_slots, "funds": self.u32(SCENARIO_FUNDS + 88 * s + 4 * c)})
        return out

    def hq_table(self) -> list[list[int]]:
        return [self.words(SCENARIO_HQ + 8 * c, 4) for c in range(CITY_COUNT)]

    def city_records(self, s: int) -> list[tuple[int, int, int, int]]:
        """(pop/100, 観光地, 経済力, (2 x 観光地 + 経済力) // 3): RAM_CITY +2/+4/+6/+10 after the start."""
        w = self.scenario_words(s)
        return [(w[5 * c], w[5 * c + 1], w[5 * c + 2], (2 * w[5 * c + 1] + w[5 * c + 2]) // 3)
                for c in range(CITY_COUNT)]

    @staticmethod
    def rank(value: int) -> str:
        """The d–s grade the city screen shows for 経済力 / 観光地 (as in the SFC version)."""
        return "dcbas"[min(max(value - 1, 0) // 20, 4)]

    # ------------------------------------------------------------ aircraft, makers

    def aircraft(self) -> list[dict]:
        ascii_names = self.strings(AIRCRAFT_ASCII, AIRCRAFT_COUNT)
        makers = {i: m for m, (first, n) in enumerate(MAKER_AIRCRAFT) for i in range(first, first + n)}
        names = self.strings(MAKER_NAME, 5)
        out = []
        for i in range(AIRCRAFT_COUNT):
            a = AIRCRAFT + AIRCRAFT_SIZE * i
            seats, rng, price, start, end, fuel, unk = self.words(a + 4, 7)
            side, top = self.words(AIRCRAFT_GFX + 4 * i, 2)
            out.append({"index": i, "name": self.cstr(self.u32(a)), "ascii": ascii_names[i],
                        "maker": names[makers[i]] if i in makers else "", "seats": seats, "range": rng * 10,
                        "price": price, "release": start, "end": end, "fuel": fuel, "unk14": unk,
                        "side_picture": side, "top_picture": None if top == 0xFFFF else top})
        return out

    def makers(self) -> list[dict]:
        names = self.strings(MAKER_NAME, 5)
        out = []
        for m in range(5):
            kind, img, pal = self.u16(MAKER_FACE + 4 * m), self.u8(MAKER_FACE + 4 * m + 2), self.u8(MAKER_FACE + 4 * m + 3)
            first, n = MAKER_AIRCRAFT[m]
            out.append({"index": m, "name": names[m], "face_kind": kind, "face_image": img, "face_palette": pal,
                        "aircraft": list(range(first, first + n)), "color": self.u16(MAKER_COLOR + 2 * m)})
        return out

    # ------------------------------------------------------------ faces

    def face_palette(self, p: int) -> list[int]:
        f = self.file(FACE_PALETTES)
        return [int.from_bytes(f[32 * p + 2 * i:32 * p + 2 * i + 2], "big") for i in range(16)]

    def face_raw(self, kind: int, img: int) -> bytes:
        f = self.file(FACE_FILES[kind][0])
        return f[FACE_BYTES * img:FACE_BYTES * (img + 1)]

    def face_pixels(self, kind: int, img: int) -> list[list[int]]:
        raw = self.face_raw(kind, img)
        out = [[0] * (FACE_W * 8) for _ in range(FACE_H * 8)]
        for t in range(FACE_W * FACE_H):
            px = decode_tile(raw[32 * t:32 * t + 32])
            tx, ty = t % FACE_W * 8, t // FACE_W * 8
            for i, v in enumerate(px):
                out[ty + i // 8][tx + i % 8] = v
        return out

    def default_palette(self, kind: int, img: int) -> int:
        if kind == 0:
            return MANAGER_PALETTE[img]
        if kind == 1:
            return img // 4
        return self.makers()[img]["face_palette"]

    def face_rgb(self, kind: int, img: int, pal: int | None = None) -> list[list[tuple[int, int, int]]]:
        colors = [md_rgb(c) for c in self.face_palette(self.default_palette(kind, img) if pal is None else pal)]
        return [[colors[v] for v in row] for row in self.face_pixels(kind, img)]

    def faces(self) -> list[dict]:
        return [{"kind": k, "file": name, "label": label, "image": i, "palette": self.default_palette(k, i)}
                for k, (_, n, name, label) in enumerate(FACE_FILES) for i in range(n)]

    # ------------------------------------------------------------ world map

    def world_map(self) -> tuple[list[int], list[int], bytes]:
        """(16 MD colours, 32 x 16 tilemap entries, 512 x 32 bytes of tiles)."""
        f = self.file(WORLD_MAP)
        pal = [int.from_bytes(f[2 * i:2 * i + 2], "big") for i in range(16)]
        tm = [int.from_bytes(f[32 + 2 * i:34 + 2 * i], "big") for i in range(MAP_W * MAP_H)]
        return pal, tm, f[32 + 2 * MAP_W * MAP_H:]

    def world_map_pixels(self) -> list[list[int]]:
        _, tm, tiles = self.world_map()
        out = [[0] * (MAP_W * 8) for _ in range(MAP_H * 8)]
        for i, e in enumerate(tm):
            t = e & 0x7FF
            px = decode_tile(tiles[32 * t:32 * t + 32])
            hf, vf = e >> 11 & 1, e >> 12 & 1
            for j, v in enumerate(px):
                x, y = j % 8, j // 8
                out[i // MAP_W * 8 + (7 - y if vf else y)][i % MAP_W * 8 + (7 - x if hf else x)] = v
        return out
