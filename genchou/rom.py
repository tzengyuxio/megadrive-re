"""MD 蒼き狼と白き牝鹿・元朝秘史 (KOEI, 1993) ROM decoding: the Japanese version and the USA one, Genghis Khan II -
Clan of the Gray Wolf.

Offsets are ROM offsets (= 68000 addresses). See docs/ROM_FORMAT.md. The program is compiled C: arguments on the
stack, memmove (src, dst, n) at $520A (J) / $51F4 (U), the decompressor (dst, src) at $8D90 / $33F0. The two
versions run the same program with different addresses and record layouts (LAYOUTS, chosen by the header serial
at 0x180): the Japanese records keep the SFC version's 16-byte names (superfamicom-re/genchou) and its women table
in block B; the USA ones shorten the names to 13 bytes and share one women table. Field meanings follow the SFC
version unless noted.
"""
import os
import sys
import unicodedata
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
from triage import load_rom

DEFAULT_ROM = os.path.join(REPO, "roms", "Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).zip")
USA_ROM = os.path.join(REPO, "roms", "Genghis Khan II - Clan of the Gray Wolf (USA).zip")


@dataclass(frozen=True)
class Layout:
    region: str                          # "J" / "U"
    serial: bytes                        # header 0x180
    # scenario loader (D2 = scenario) and where it returns; see SCENARIO_COUNT below
    loader: int
    loader_end: int
    scenario_a: int                      # 4 pointers: block A -> $FF0000
    scenario_b: int                      # 4 pointers: block B -> b_ram
    a_size: int
    b_ram: int
    b_size: int
    year_at: int                         # in block B, BE16
    # persons: name, then house, country, 体力, 戦闘/政治, 魅力/指揮, 年齢, culture bits, status (name_len + 0..7)
    person_size: int
    name_len: int
    face_at: int                         # BE16
    countries_at: int
    houses_at: int
    house_size: int
    house_name: int                      # name bytes; then first country, king (RAM pointers)
    house_woman: int | None              # ROM pointer to the woman (USA only)
    house_culture: int
    # the player's family blocks: FAMILIES[6 * scenario + k] (0 = none) for house FAMILY_HOUSES[...]; 8 person
    # slots, then the children (name, then 4 unknown bytes, the face code)
    families: int
    family_houses: int
    family_size: int
    family_ram: int                      # the loader copies the first 2 blocks of scenario 1 here
    children_at: int
    child_size: int
    child_name: int
    child_face: int
    child_slots: int
    # women: (J) per scenario, up to 32 slots at block B +0; (U) one table at women_table
    women_table: int | None
    women_slots: int
    woman_size: int
    woman_name: int
    woman_country: int
    woman_face: int
    place_names: int                     # 2 x 33 names (Mongolia, world)
    place_len: int
    place_ram: int
    place_x: int                         # 2 x (33 x, 33 y) bytes, 0x42 apart: label positions on the map
    label_ram: int                       # x at label_ram, y at label_ram + 0x22
    # faces
    portraits: int
    face_palette: int
    head_layout: int                     # 8 groups x 7 heads x word: layout number
    face_layouts: int                    # 22 layouts x 5 parts x (first tile, tile count) words
    part_tiles: int                      # 8 groups x 7 heads x 2 versions x 5 parts x long pointer (raw tiles)


LAYOUTS = {
    "J": Layout(
        region="J", serial=b"GM T-76103", loader=0x276FC, loader_end=0x2783E,
        scenario_a=0x63A44, scenario_b=0x63A54, a_size=0x1564, b_ram=0x1808, b_size=0x553, year_at=0x54E,
        person_size=26, name_len=16, face_at=24, countries_at=0xB14, houses_at=0x11C8, house_size=28, house_name=18,
        house_woman=None, house_culture=26,
        families=0x639E4, family_houses=0x6394A, family_size=0x152, family_ram=0x1564, children_at=0xD0,
        child_size=22, child_name=16, child_face=20, child_slots=5,
        women_table=None, women_slots=32, woman_size=22, woman_name=15, woman_country=18, woman_face=20,
        place_names=0x60C72, place_len=16, place_ram=0x8568, place_x=0x60BEE, label_ram=0x1D62,
        portraits=0x9F11A, face_palette=0x5F63E, head_layout=0x5F08C, face_layouts=0x5F0FC, part_tiles=0x5F6C6),
    "U": Layout(
        region="U", serial=b"GM T-76066", loader=0x26250, loader_end=0x26384,
        scenario_a=0x4B944, scenario_b=0x4B954, a_size=0x1592, b_ram=0x1826, b_size=0x27D, year_at=0x278,
        person_size=24, name_len=13, face_at=22, countries_at=0xA3A, houses_at=0x10EE, house_size=36, house_name=22,
        house_woman=30, house_culture=34,
        families=0x4B8E4, family_houses=0x4B848, family_size=0x138, family_ram=0x1592, children_at=0xC0,
        child_size=20, child_name=13, child_face=18, child_slots=6,
        women_table=0x4562C, women_slots=20, woman_size=18, woman_name=13, woman_country=15, woman_face=16,
        place_names=0x48DD2, place_len=15, place_ram=0x8114, place_x=0x48D4E, label_ram=0x1AAA,
        portraits=0x7D272, face_palette=0x475DA, head_layout=0x46E74, face_layouts=0x46EE4, part_tiles=0x47662),
}

# Scenarios: 4 (the 4th, 1185, is not in the menu: after scenario 1's Mongolia is unified the game continues
# with it). The loader copies block A (2 bytes, persons, countries, houses) to $FF0000, block B (J: the women,
# running state and the start year; U: running state and the start year) to b_ram, the first two family blocks
# of scenario 1 to family_ram, the place names of the map (Mongolia for scenario 1, else the world) to place_ram
# and the label positions to label_ram.
SCENARIO_COUNT = 4
PERSONS_AT, PERSON_SLOTS = 2, 109
COUNTRY_SIZE, COUNTRY_SLOTS = 52, 33
HOUSE_SLOTS = 33
# After copying scenario 4 the loader empties person slot 69 (status = 0x80), as in the SFC version
LOADER_EMPTIES = {3: [69]}
FAMILY_SLOTS = 8
MONGOL_COUNTRIES = 14

# USA text is ASCII, 0-terminated. The 8x16 font ($40 + 2 * (c - $20) in VRAM) draws some punctuation as roman
# numerals: '{|' is VIII and '}~' is IV.
GLYPHS = {"$": "I", "\\": "II", "^": "III", "@": "V", "=": "X", "{": "V", "|": "III", "}": "IV", "~": ""}

# Faces: 40x48 = 5x6 4bpp tiles row-major (960 bytes), drawn by J $7A6C / U $7752 (persons) and J $7AE6 / U $77CC
# (women). Code bit 15 clear and
# <= 0x62: portrait n = code (women: code + WOMAN_PORTRAIT), a compressed 960-byte image. Bit 15 set: composed face,
# see face_tiles. Both use palette line 1 = face_palette. Both versions have the same portraits and parts.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_COUNT = 97
WOMAN_PORTRAIT = 0x39
PART_NAMES = ["eyes", "nose", "mouth", "top", "body"]
PART_BITS = [6, 5, 4, 8, 7]              # code bit choosing version 1 of each part (fields 0-4)
DRAW_ORDER = [3, 4, 0, 1, 2]             # the composer copies top, body, eyes, nose, mouth
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def layout(rom: bytes) -> Layout:
    return next(lay for lay in LAYOUTS.values() if rom[0x180:0x180 + len(lay.serial)] == lay.serial)


def load(path: str = DEFAULT_ROM) -> bytes:
    return load_rom(path)


def be16(b: bytes, a: int) -> int:
    return b[a] << 8 | b[a + 1]


def be32(b: bytes, a: int) -> int:
    return int.from_bytes(b[a:a + 4], "big")


def text(b: bytes) -> str:
    """USA: ASCII with roman-numeral glyphs. Japanese: Shift-JIS; ESC K switches to half-width katakana (JIS X 0201,
    shown as full-width here) until ESC H, where '-' is the long vowel ー. Kanji (SJIS lead bytes) can appear in
    either mode."""
    if b"\x1b" not in b and all(c < 0x80 for c in b.split(b"\0")[0]):
        s = b.split(b"\0")[0].decode("latin-1")
        return "".join(GLYPHS.get(c, c) for c in s)
    out, kana, i = [], False, 0
    while i < len(b) and b[i]:
        c = b[i]
        if c == 0x1B:
            kana = b[i + 1] == 0x4B
            i += 2
        elif 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF:
            out.append(b[i:i + 2].decode("shift_jis"))
            i += 2
        elif 0xA1 <= c <= 0xDF:
            out.append(unicodedata.normalize("NFKC", bytes([c]).decode("shift_jis")))
            i += 1
        else:
            out.append("ー" if kana and c == 0x2D else chr(c))
            i += 1
    return unicodedata.normalize("NFC", "".join(out))    # half-width ﾞ ﾟ become combining marks: compose them


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


# --- scenarios ---------------------------------------------------------------------------------------------

def block_a(rom: bytes, n: int) -> bytes:
    L = layout(rom)
    a = be32(rom, L.scenario_a + 4 * n)
    return rom[a:a + L.a_size]


def block_b(rom: bytes, n: int) -> bytes:
    L = layout(rom)
    a = be32(rom, L.scenario_b + 4 * n)
    return rom[a:a + L.b_size]


def year(rom: bytes, n: int) -> int:
    return be16(block_b(rom, n), layout(rom).year_at)


def person(rec: bytes, L: Layout) -> dict:
    """Person record: name, then the SFC version's +16.. fields (USA: from +13, with a 0 byte before the face)."""
    o = L.name_len
    return {
        "name": text(rec[:o]),
        "house": rec[o],                 # 0xFF = none
        "country": rec[o + 1],
        "hp": rec[o + 2] >> 4, "hp_max": rec[o + 2] & 15,
        "war": rec[o + 3] >> 4, "pol": rec[o + 3] & 15,      # 0-4 = E-A
        "cha": rec[o + 4] >> 4, "lead": rec[o + 4] & 15,
        "age": rec[o + 5] - 256 if rec[o + 5] > 127 else rec[o + 5],
        "culture": rec[o + 6] >> 2 & 7,  # bits 2-4 (SFC +22; inferred)
        "flags": rec[o + 6] & 0xE3,
        "status": rec[o + 7],            # 3 = king, 0x80 = empty slot
        "face": be16(rec, L.face_at),
    }


def persons(rom: bytes, n: int) -> list[dict]:
    """Used person slots of scenario n, with their slot number."""
    L = layout(rom)
    a = block_a(rom, n)
    out = []
    for k in range(PERSON_SLOTS):
        rec = a[PERSONS_AT + L.person_size * k:PERSONS_AT + L.person_size * (k + 1)]
        if rec[L.name_len + 7] != 0x80 and rec[0] and k not in LOADER_EMPTIES.get(n, []):
            out.append({"slot": k, **person(rec, L)})
    return out


def families(rom: bytes, n: int) -> list[dict]:
    """The family blocks of scenario n: {house, persons, children} for each house the player can choose."""
    L = layout(rom)
    out = []
    for k in range(6):
        p = be32(rom, L.families + 24 * n + 4 * k)
        if not p:
            continue
        rows = []
        for j in range(FAMILY_SLOTS):
            rec = rom[p + L.person_size * j:p + L.person_size * (j + 1)]
            if rec[0] and rec[L.name_len + 7] != 0x80:
                rows.append({"slot": j, **person(rec, L)})
        kids = []
        for j in range(L.child_slots):
            rec = rom[p + L.children_at + L.child_size * j:p + L.children_at + L.child_size * (j + 1)]
            if not rec[0]:
                break
            kids.append({"name": text(rec[:L.child_name]), "raw": rec[L.child_name:].hex(" "),
                         "face": be16(rec, L.child_face)})
        out.append({"house": rom[L.family_houses + 6 * n + k], "address": p, "persons": rows, "children": kids})
    return out


def countries(rom: bytes, n: int) -> list[dict]:
    L = layout(rom)
    a = block_a(rom, n)
    out = []
    for k in range(MONGOL_COUNTRIES if n == 0 else COUNTRY_SLOTS):
        r = a[L.countries_at + COUNTRY_SIZE * k:L.countries_at + COUNTRY_SIZE * (k + 1)]
        out.append({
            "id": k,
            "b0": be32(r, 0),             # 0 in ROM
            "house": r[4],
            "adjacent": [x for x in r[5:10] if x != 0xFF],
            "gold": be16(r, 10), "food": be16(r, 12), "population": be16(r, 14),
            "mix": list(r[16:20]),        # 住民配分 % (farming, herding, crafts, town; FC inference)
            "b20": r[20],
            "v21": r[21], "v22": r[22], "v23": r[23],   # the 3 numbers right of the country panel
            "troops": list(r[24:40]),     # 16 unit types (FC inference)
            "rest": r[40:].hex(" "),
        })
    return out


def houses(rom: bytes, n: int) -> list[dict]:
    L = layout(rom)
    a = block_a(rom, n)
    out = []
    for k in range(HOUSE_SLOTS):
        r = a[L.houses_at + L.house_size * k:L.houses_at + L.house_size * (k + 1)]
        if not r[0]:
            continue
        o = L.house_name
        first, king = be32(r, o), be32(r, o + 4)
        woman = be32(r, L.house_woman) if L.house_woman else 0
        out.append({
            "id": k, "name": text(r[:o]),
            "first_country": (first - 0xFF0000 - L.countries_at) // COUNTRY_SIZE if first else None,
            "king": (king - 0xFF0000 - PERSONS_AT) // L.person_size if king else None,
            "woman": (woman - L.women_table) // L.woman_size if woman else None,
            "culture": r[L.house_culture], "b35": r[L.house_culture + 1],
        })
    return out


def women(rom: bytes, n: int = 0) -> list[dict]:
    """The women of scenario n (Japanese: block B, up to the first empty name; USA: one table for all scenarios).
    Fields between the name and the country are not decoded (SFC: +15 FF, +16, +17)."""
    L = layout(rom)
    base = L.women_table if L.women_table else be32(rom, L.scenario_b + 4 * n)
    out = []
    for k in range(L.women_slots):
        r = rom[base + L.woman_size * k:base + L.woman_size * (k + 1)]
        if not r[0]:
            break
        out.append({"id": k, "name": text(r[:L.woman_name]), "raw": r[L.woman_name:L.woman_country].hex(" "),
                    "country": r[L.woman_country], "face": be16(r, L.woman_face)})
    return out


def place_names(rom: bytes, world: bool) -> list[str]:
    L = layout(rom)
    a = L.place_names + 33 * L.place_len * world
    return [text(rom[a + L.place_len * k:a + L.place_len * (k + 1)]) for k in range(33)]


def place_pos(rom: bytes, world: bool) -> list[tuple[int, int]]:
    L = layout(rom)
    x = L.place_x + 0x42 * world
    return [(rom[x + k], rom[x + 0x21 + k]) for k in range(33)]


# --- faces -------------------------------------------------------------------------------------------------

_MASK = [(1 << k) - 1 for k in range(17)]


def decompress(rom: bytes, src: int) -> bytes:
    """The decompressor (J $8D90, U $33F0): a flag byte per 8 items, MSB first; set = literal byte, clear = copy.
    The copy length and distance are prefix codes read from a 16-bit window over a bit stream of little-endian words
    (U: bit reader $3376); the flag and literal bytes are read from the same pointer between the words."""
    s = src
    win = buf = avail = 0

    def getbits(n: int) -> None:
        nonlocal win, buf, avail, s
        win = (win << n) & 0xFFFF
        if n > avail:
            n -= avail
            win |= ((_MASK[avail] & buf) << n) & 0xFFFF
            buf = rom[s + 1] << 8 | rom[s]
            s += 2
            avail = 16 - n
        else:
            avail -= n
        win |= (buf >> avail) & _MASK[n]

    out = bytearray()
    getbits(16)
    while True:
        flags = rom[s]
        s += 1
        for _ in range(8):
            if flags & 0x80:
                out.append(rom[s])
                s += 1
            else:
                w = win
                if w & 0x8000:           # length codes: 1 / 01x / 001xx / ... (the 1-bit code isn't consumed)
                    length = 1
                else:
                    for bit, shift, nbits in ((0x4000, 13, 2), (0x2000, 11, 4), (0x1000, 9, 6), (0x800, 7, 8),
                                              (0x400, 5, 10), (0x200, 3, 12)):
                        if w & bit:
                            length = (w >> shift) & ((bit << 1 >> shift) - 1)
                            getbits(nbits)
                            break
                    else:
                        length = ((w & 0x1FC) >> 2) + 0x80
                        if length == 0xFF:
                            return bytes(out)
                        getbits(13)
                win &= 0x7FFF
                w = win
                if w < 0x800:
                    d = (w & 0x600) >> 9
                    getbits(7)
                elif w < 0xC00:
                    d = ((w & 0x300) >> 8) + 4
                    getbits(8)
                elif w < 0x1800:
                    d = (((w - 0xC00) & 0xF80) >> 7) + 8
                    getbits(9)
                elif w < 0x3000:
                    d = (((w - 0x1800) & 0x1FC0) >> 6) + 0x20
                    getbits(10)
                else:
                    k = min(w >> 12, 7)
                    d = ((w & 0x1FFF) | 0x1000) >> (8 - k)
                    getbits(8 + k)
                p = len(out) - d - 1
                for i in range(length + 1):
                    out.append(out[p + i])
            flags = (flags << 1) & 0xFF


def portrait_tiles(rom: bytes, n: int) -> bytes:
    return decompress(rom, be32(rom, layout(rom).portraits + 4 * n))


def face_fields(code: int) -> dict:
    """group = bits 12-14, head type = bits 9-11 mod 7, part versions from PART_BITS."""
    g, m = code >> 12 & 7, (code >> 9 & 7) % 7
    return {"group": g, "type": m, "head": 7 * g + m, "variants": [code >> b & 1 for b in PART_BITS]}


def head_parts(rom: bytes, head: int) -> list[dict]:
    """The 5 parts of head 7 * group + type: face tiles covered and the two versions' source addresses."""
    L = layout(rom)
    g, m = divmod(head, 7)
    lay = be16(rom, L.head_layout + 2 * head)
    out = []
    for k in range(5):
        first, count = be16(rom, L.face_layouts + 20 * lay + 4 * k), be16(rom, L.face_layouts + 20 * lay + 4 * k + 2)
        src = [be32(rom, L.part_tiles + 0x118 * g + 4 * (v * 5 + m * 10 + k)) for v in range(2)]
        out.append({"name": PART_NAMES[k], "cells": list(range(first, first + count)), "src": src,
                    "layout": lay})
    return out


def face_tiles(rom: bytes, code: int, woman: bool = False) -> bytes:
    """960 bytes of 4bpp tiles the game puts in VRAM for a face code."""
    if not code & 0x8000 and code <= 0x62:
        return portrait_tiles(rom, code + (WOMAN_PORTRAIT if woman else 0))
    f = face_fields(code)
    buf = bytearray(FACE_BYTES)
    parts = head_parts(rom, f["head"])
    for k in DRAW_ORDER:
        p = parts[k]
        src = p["src"][f["variants"][k]]
        buf[32 * p["cells"][0]:32 * (p["cells"][-1] + 1)] = rom[src:src + 32 * len(p["cells"])]
    return bytes(buf)


def tiles_pixels(tiles: bytes) -> list[int]:
    """40x48 colour indices (row-major) of 30 row-major 4bpp tiles."""
    w = FACE_W * 8
    px = [0] * (w * FACE_H * 8)
    for t in range(FACE_W * FACE_H):
        d = tiles[32 * t:32 * t + 32]
        cx, cy = t % FACE_W * 8, t // FACE_W * 8
        for y in range(8):
            for x in range(8):
                px[(cy + y) * w + cx + x] = d[y * 4 + x // 2] >> (4 if x % 2 == 0 else 0) & 15
    return px


def face_palette(rom: bytes) -> list[tuple[int, int, int]]:
    return [md_rgb(be16(rom, layout(rom).face_palette + 2 * i)) for i in range(16)]
