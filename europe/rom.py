"""MD ヨーロッパ戦線 Europa Sensen (KOEI, 1993) ROM decoding.

Offsets are file offsets of the 1 MB ROM (= 68000 addresses). See docs/ROM_FORMAT.md. The data is the SFC
version's (superfamicom-re/europe) with 16-bit fields big-endian and word-aligned; the scenario blocks, faces and
battle map terrain match it byte for byte. Text is Shift-JIS with half-width kana runs (ESC K katakana, ESC H
hiragana). Compressed data (faces, battle maps) is KOEI LZ, decoded by the table-free decoder of haouden/lz.py
(the game's decoder is $3360).
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.append(os.path.join(REPO, "haouden"))  # last, so haouden/verify_*.py never shadow ours
import lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Europa Sensen (Japan).zip")

# Text: Shift-JIS kanji / full-width, half-width kana runs: ESC K = katakana (the default at the start of a
# string), ESC H = hiragana; the mode carries over to the next line of a multi-line text. In katakana '-' is ー.
# In weapon names '$' is Ⅰ and "'" is Ⅱ (as in the SFC version, where the weapons screen shows it).
HALF_WIDTH_SIGNS = {"$": "Ⅰ", "'": "Ⅱ"}

# Nationality bits (person +9, weapon +3); names from the flags the SFC version draws, not ROM strings
NATIONS = {0x01: "ドイツ", 0x02: "イタリア", 0x04: "アメリカ", 0x08: "イギリス", 0x10: "フランス", 0x20: "ソ連"}
AXIS_BITS = 0x03

# Scenarios: index 0 is the campaign (キャンペーンモード, starts with scenario 1's block), 1-6 the scenarios.
# Starting scenario k ($9DC4) copies BLOCKS[k] (BLOCK_SIZE bytes) to RAM $FF0000 with memmove $7E8C, then the
# battle map's terrain (LZ, TERRAIN[k]) to $FF259E.
SCENARIO_COUNT = 6
SCENARIO_MENU = 0x6A7B8                  # 7 pointers: campaign line, then "1 ﾌﾗﾝｽ侵攻戦  1940年 5月10日" ...
SCENARIO_BLOCKS = 0x6A730                # 7 pointers ($9DF6); [0] (0x4EF4C) is not used, the campaign takes [1]
BLOCK_SIZE = 0x2495
BLOCK_RAM = 0xFF0000
# Block header: +0 0, +1 map number (bit 7 set by the campaign, $9D80), +2 year - 1940, +3 month, +4 day
GENERALS_AT, GENERAL_SIZE, GENERAL_SLOTS = 0x1EA, 22, 40     # slots 0-19 Axis, 20-39 Allies; +9 = FF empty
CITIES_AT, CITY_SIZE = 0x1F2A, 66                            # until a record without a name
CITY_MAX = (BLOCK_SIZE - CITIES_AT) // CITY_SIZE             # 21
CITY_SLOTS = 6
LEADERS = 0x6AF1E                        # 6 records in the general format: ヒトラー ... ワシレフスキー
LEADER_COUNT = 6
PERSON_COUNT = 94                        # person ids 0-93 appear in the scenarios, 94-99 are the leaders
BIOGRAPHIES = 0x758C0                    # 94 x 7 pointers: 7 lines per person id
BIO_LINES = 7

# Weapons: 158 records of 16 bytes (+0 name pointer, +4-+14 = the SFC record's +3-+13, +15 padding)
WEAPONS = 0x6AFC6
WEAPON_SIZE = 16
WEAPON_COUNT = 158
WEAPON_KINDS = ["歩兵", "自動車化歩兵", "装甲歩兵", "戦車・自走砲", "砲・対戦車砲", "工兵", "修理兵", "補給兵"]

# Faces: $8388(x, y, general) decodes portrait general[+20] (the person id) from FACES (LZ, 960 bytes = 5x6
# 4bpp tiles row-major) to VRAM tile 0x340 and loads FACE_PALETTE to CRAM line 0. 120 portraits: 0-93 the
# generals, 94-99 the leaders; 100-119 belong to no person and are drawn by number ($8468):
#   航空隊 reports ($3185A, 「%s航空隊より報告」): faces 100 / 104 / 105 with the names AIR_NAMES[0 / 1 / 2]
#     (0 when the player is the Axis ($FF002E = 0), 2 on maps 2 and 5 (the Soviet fronts), 1 otherwise);
#   特殊工作 ($30E60: 奇襲, 破壊活動, 通信切断, 暗殺, 情報収集): faces 0x65 + k (101-103), names AGENT_NAMES[k]
#     (k = 2 for the Axis, 1 on maps 2 and 5, 0 otherwise);
#   副官 of a division ($1FC90, 「第%d師団 副官」): face $FF6A10[side], set to ADJUTANT_FIRST ($62BA) and stepped
#     by $840A up to ADJUTANT_LAST, then back by 5 (Axis 106-111, Allies 112-117);
#   events: face 118 (MARGARETE, 「私ノ手作リノパイを持って参りました」, lines 0x6F928) and 119 (SISTER, lines
#     0x6F910).
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
FACES = 0xC2A46
FACE_COUNT = 120
FACE_PALETTE = 0x697FE
FACE_VRAM = 0x6800
AIR_FACES, AIR_NAMES = (100, 104, 105), 0x6F29C        # 3 pointers: ゲーリング, ホーカー, ツポレフ
AGENT_FACE, AGENT_NAMES = 0x65, 0x6F26C                 # 3 pointers: マクドナルド, ケンタスキー, ハーゲンダッツ
ADJUTANT_FIRST, ADJUTANT_LAST = (0x62BD, 0x62C5), 0x6A386  # immediates of the two move.b; 2-byte limit table
MARGARETE, SISTER = 0x4AB50, 0x4AB20                    # the names over faces 118 and 119
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values

# Battle maps: map m = block +1 & 0x7F, 40x40 cells.
#   Terrain: LZ at the pointer TERRAIN + 4k (scenario k = 1-6; $9E24) -> RAM $FF259E; low nibble = terrain.
#   Cells: LZ at the pointer MAP_CELLS + 4m ($9E7A) -> cell code c -> word w = BE16 at MAP_WORDS + 0x110 m + 2c,
#   stored as (w & 0xF) * 2 + (w & 0xFFF0) to RAM $FF6D30 (40 words a row; $9E56). How these words become the
#   picture is not solved.
TERRAIN = 0x603A0
MAP_CELLS = 0x61616
MAP_WORDS = 0x6BAAE
MAP_SIZE = 40
MAP_COUNT = 6
TERRAIN_RAM = 0xFF259E
CELLS_RAM = 0xFF6D30
TERRAIN_NAMES = ["進入不可", "都市", "道路", "平地", "砂漠", "川", "湿地", "荒地", "森林", "丘陵", "橋"]   # SFC $C1:E017


def be16(raw: bytes, i: int) -> int:
    return raw[i] << 8 | raw[i + 1]


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            return z.read(z.namelist()[0])
    with open(path, "rb") as f:
        return f.read()


def nations(bits: int) -> str:
    return "・".join(n for b, n in NATIONS.items() if bits & b)


def kana_text(run: bytes, kata: bool) -> str:
    s = unicodedata.normalize("NFKC", run.decode("cp932", "replace"))
    if kata:
        s = s.replace("-", "ー")
    else:
        s = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)
    return "".join(HALF_WIDTH_SIGNS.get(c, c) for c in s)


def tiles_pixels(tiles: bytes, w: int, h: int) -> list[int]:
    """MD 4bpp tiles (row-major, w x h) -> colour numbers, row-major."""
    out = [0] * (w * h * 64)
    for t in range(w * h):
        for y in range(8):
            for x in range(8):
                b = tiles[32 * t + 4 * y + x // 2]
                out[(t // w * 8 + y) * w * 8 + t % w * 8 + x] = b >> 4 if x % 2 == 0 else b & 15
    return out


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        assert self.data[0x180:0x18E] == b"GM T-76113 -10", self.data[0x180:0x18E]

    def ptr(self, at: int) -> int:
        return int.from_bytes(self.data[at:at + 4], "big")

    def lz(self, at: int) -> bytes:
        return lz.decompress(self.data, at)[0]

    def text(self, raw: bytes, kata: bool = True) -> tuple[str, bool]:
        """Game text -> (str, kana mode at the end). NUL ends; ESC K / ESC H switch katakana / hiragana."""
        out, run = [], bytearray()

        def flush() -> None:
            if run:
                out.append(kana_text(bytes(run), kata))
                run.clear()

        i = 0
        while i < len(raw) and raw[i]:
            b = raw[i]
            if b == 0x1B and i + 1 < len(raw):
                flush()
                if raw[i + 1] in b"KH":
                    kata = raw[i + 1] == ord("K")
                i += 2
            elif (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC) and i + 1 < len(raw):
                flush()
                out.append(raw[i:i + 2].decode("cp932", "replace"))
                i += 2
            else:
                run.append(b)
                i += 1
        flush()
        return "".join(out), kata

    def string(self, at: int, limit: int = 80) -> str:
        return self.text(self.data[at:at + limit])[0]

    # --- scenarios ---
    def block_offset(self, sc: int) -> int:
        """ROM offset of the block of scenario sc (1-6)."""
        return self.ptr(SCENARIO_BLOCKS + 4 * sc)

    def block(self, sc: int) -> bytes:
        o = self.block_offset(sc)
        return self.data[o:o + BLOCK_SIZE]

    def scenarios(self) -> list[dict]:
        """Menu line and block header (map, date) of scenarios 1-6."""
        out = []
        for sc in range(1, SCENARIO_COUNT + 1):
            line = self.string(self.ptr(SCENARIO_MENU + 4 * sc))
            b = self.block(sc)
            out.append({"id": sc, "title": line.split()[1], "menu": line, "map": b[1], "year": 1940 + b[2],
                        "month": b[3], "day": b[4], "header": b[:16]})
        return out

    @staticmethod
    def general(r: bytes, slot: int | None = None) -> dict:
        """22 bytes (as SFC): +0 name (9, half-width katakana, NUL padded), +9 nationality bits, +10 指揮,
        +11 魅力, +12 unknown, +13 / +14 unknown (equal), +15 歩兵, +16 砲兵, +17 戦車, +18 経験, +19 unknown,
        +20 person id, +21 unknown (leaders: 04 / 05)."""
        return {"slot": slot, "raw": r, "name": kana_text(r[:9].split(b"\0")[0], True).strip(), "nation": r[9],
                "指揮": r[10], "魅力": r[11], "unknown12": r[12], "unknown13": r[13], "unknown14": r[14],
                "歩兵": r[15], "砲兵": r[16], "戦車": r[17], "経験": r[18], "unknown19": r[19], "id": r[20],
                "unknown21": r[21]}

    def generals(self, sc: int) -> list[dict]:
        """Occupied general slots of scenario sc (1-6; slots 0-19 Axis, 20-39 Allies)."""
        b = self.block(sc)
        out = []
        for k in range(GENERAL_SLOTS):
            o = GENERALS_AT + GENERAL_SIZE * k
            if b[o + 9] != 0xFF:
                out.append(self.general(b[o:o + GENERAL_SIZE], k))
        return out

    def leaders(self) -> list[dict]:
        return [self.general(self.data[LEADERS + GENERAL_SIZE * k:LEADERS + GENERAL_SIZE * (k + 1)], k)
                for k in range(LEADER_COUNT)]

    def persons(self) -> list[dict]:
        """Person ids 0-99: the record of each id's first scenario (the records of an id are the same in every
        scenario), then the leaders; with the scenarios (1-6) each id appears in."""
        seen: dict[int, dict] = {}
        for sc in range(1, SCENARIO_COUNT + 1):
            for g in self.generals(sc):
                p = seen.setdefault(g["id"], dict(g, scenarios=[], side=[]))
                p["scenarios"].append(sc)
                p["side"].append("枢軸" if g["slot"] < 20 else "連合")
        for g in self.leaders():
            seen[g["id"]] = dict(g, scenarios=[], side=["枢軸" if g["nation"] & AXIS_BITS else "連合"])
        return [seen[k] for k in sorted(seen)]

    def bio_pointer(self, pid: int, line: int) -> int:
        return self.ptr(BIOGRAPHIES + 4 * (BIO_LINES * pid + line))

    def biography(self, pid: int) -> list[str]:
        """The 7 lines of person pid (0-93); the kana mode carries over."""
        lines, kata = [], True
        for k in range(BIO_LINES):
            s, kata = self.text(self.data[self.bio_pointer(pid, k):][:120], kata)
            lines.append(s)
        return lines

    def cities(self, sc: int) -> list[dict]:
        """66 bytes: +0 name (11), +11 x, +12 y (map cell), +13 padding, +14 弾薬 +16 燃料 +18 食料 (BE16),
        +20 +22 +24 the same three again (unknown), +26 耐久, +27 耐久 maximum, +28 6 garrison slots of 6 bytes
        (weapon id (FF none), padding, count BE16, 2 unknown bytes), +64 flags (bit 4 side: 1 連合, 0 枢軸),
        +65 padding. Field meanings as the SFC version (58 bytes, LE16, no padding)."""
        b = self.block(sc)
        out = []
        for k in range(CITY_MAX):
            o = CITIES_AT + CITY_SIZE * k
            r = b[o:o + CITY_SIZE]
            name = self.text(r[:11])[0]
            if not name:
                break
            garrison = []
            for j in range(CITY_SLOTS):
                g = r[28 + 6 * j:34 + 6 * j]
                if g[0] != 0xFF:
                    garrison.append({"weapon": g[0], "count": be16(g, 2), "unknown": g[4:6]})
            out.append({"id": k, "raw": r, "name": name, "x": r[11], "y": r[12],
                        "弾薬": be16(r, 14), "燃料": be16(r, 16), "食料": be16(r, 18),
                        "values2": [be16(r, 20), be16(r, 22), be16(r, 24)], "耐久": r[26], "耐久max": r[27],
                        "garrison": garrison, "flags": r[64], "side": "連合" if r[64] & 0x10 else "枢軸"})
        return out

    # --- weapons ---
    def weapons(self) -> list[dict]:
        """16 bytes: +0 name pointer, +4 nationality bits, +5 available from (inferred: high nibble year - 1940,
        low nibble month), +6 kind (WEAPON_KINDS, inferred), +7 AT, +8 AP, +9 防, +10 速, +11 +12 unknown,
        +13 射, +14 unknown, +15 padding."""
        out = []
        for i in range(WEAPON_COUNT):
            o = WEAPONS + WEAPON_SIZE * i
            r = self.data[o:o + WEAPON_SIZE]
            out.append({"id": i, "raw": r, "name": self.string(self.ptr(o), 24), "nation": r[4], "available": r[5],
                        "kind": r[6], "AT": r[7], "AP": r[8], "防": r[9], "速": r[10], "unknown10": r[11],
                        "unknown11": r[12], "射": r[13], "unknown13": r[14]})
        return out

    # --- faces ---
    def face_tiles(self, n: int) -> bytes:
        return self.lz(self.ptr(FACES + 4 * n))[:FACE_BYTES]

    def face_palette(self) -> list[int]:
        return [be16(self.data, FACE_PALETTE + 2 * i) for i in range(16)]

    def face_pixels(self, n: int) -> list[int]:
        """40x48 colour numbers of portrait n, row-major."""
        return tiles_pixels(self.face_tiles(n), FACE_W, FACE_H)

    def unused_portraits(self) -> dict[int, dict]:
        """Portraits 100-119 (no person) -> {"group", "name"?} from the code that draws them."""
        out = {}
        for k, f in enumerate(AIR_FACES):
            out[f] = {"group": "航空隊", "name": self.string(self.ptr(AIR_NAMES + 4 * k)).strip()}
        for k in range(3):
            out[AGENT_FACE + k] = {"group": "特殊工作", "name": self.string(self.ptr(AGENT_NAMES + 4 * k)).strip()}
        for side, at in zip(("軸心國", "聯合軍"), ADJUTANT_FIRST):
            for f in range(self.data[at], self.data[ADJUTANT_LAST + (side == "聯合軍")] + 1):
                out[f] = {"group": f"副官（{side}）"}
        out[118] = {"group": "事件人物", "name": self.string(MARGARETE)}
        out[119] = {"group": "事件人物", "name": self.string(SISTER)}
        return dict(sorted(out.items()))

    def face_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = [md_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(n)]

    # --- battle maps ---
    def map_number(self, sc: int) -> int:
        return self.block(sc)[1] & 0x7F

    def terrain_raw(self, sc: int) -> bytes:
        """The 1600 terrain bytes of scenario sc's map (1-6) as the game copies them to $FF259E."""
        return self.lz(self.ptr(TERRAIN + 4 * sc))

    def map_terrain(self, sc: int) -> list[int]:
        return [v & 15 for v in self.terrain_raw(sc)]

    def map_cells(self, m: int) -> bytes:
        return self.lz(self.ptr(MAP_CELLS + 4 * m))

    def map_words(self, m: int) -> list[int]:
        """1600 words as $9E56 stores them at $FF6D30."""
        out = []
        for c in self.map_cells(m):
            w = be16(self.data, MAP_WORDS + 0x110 * m + 2 * c)
            out.append(((w & 0xF) * 2 + (w & 0xFFF0)) & 0xFFFF)
        return out
