"""MD Genghis Khan II - Clan of the Gray Wolf (KOEI, 1993; 蒼き狼と白き牝鹿・元朝秘史, USA) ROM decoding.

Offsets are ROM offsets (= 68000 addresses). See docs/ROM_FORMAT.md. The program is compiled C: arguments on the
stack, memmove at $51F4 (src, dst, n), the decompressor at $33F0 (dst, src). The tables follow the SFC version
(superfamicom-re/genchou) with 68000 pointers and big-endian numbers; field meanings follow it unless noted.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
from triage import load_rom

DEFAULT_ROM = os.path.join(REPO, "roms", "Genghis Khan II - Clan of the Gray Wolf (USA).zip")

# Text is ASCII, 0-terminated. The 8x16 font ($40 + 2 * (c - $20) in VRAM) draws some punctuation as roman
# numerals: '{|' is VIII and '}~' is IV.
GLYPHS = {"$": "I", "\\": "II", "^": "III", "@": "V", "=": "X", "{": "V", "|": "III", "}": "IV", "~": ""}

# Scenarios: 4 (the 4th, "World Conquest" 1185, is not in the menu: after scenario 1's Mongolia is unified the
# game continues with it). The loader at $26250 (D2 = scenario) copies
#   block A [SCENARIO_A + 4n] -> $FF0000, 0x1592 bytes: 2 bytes, persons, countries, houses
#   block B [SCENARIO_B + 4n] -> $FF1826, 0x27D bytes: running state (zero in ROM) and the start year
#   FAMILIES[0]               -> $FF1592, 0x270 bytes (the first two family blocks of scenario 1)
#   PLACE_NAMES[world]        -> $FF8114, 0x1EF; PLACE_X / PLACE_Y [world] -> $FF1AAA / $FF1ACC, 0x21 each
SCENARIO_COUNT = 4
SCENARIO_A = 0x4B944
SCENARIO_B = 0x4B954
A_SIZE, B_SIZE = 0x1592, 0x27D
PERSONS_AT, PERSON_SIZE, PERSON_SLOTS = 2, 24, 109
COUNTRIES_AT, COUNTRY_SIZE, COUNTRY_SLOTS = 0xA3A, 52, 33
HOUSES_AT, HOUSE_SIZE, HOUSE_SLOTS = 0x10EE, 36, 33
YEAR_AT = 0x278                          # in block B, BE16
# After copying scenario 4 the loader empties person slot 69 (status = 0x80, $262F4), as in the SFC version
LOADER_EMPTIES = {3: [69]}
# The player's family: FAMILIES[6 * scenario + k] (0 = none) is a 0x138-byte block for house FAMILY_HOUSES[...]:
# 8 person slots, then from +0xC0 the children, 20-byte records (name, 7 bytes not decoded; +13 is probably the
# age: Joti 2 in 1184, 24 in 1206). $26202 copies the chosen house's block to $FF1592 when a game starts.
FAMILIES = 0x4B8E4
FAMILY_HOUSES = 0x4B848
FAMILY_SLOTS = 8
CHILDREN_AT, CHILD_SIZE, CHILD_SLOTS = 0xC0, 20, 6
WOMAN_SIZE = 18                          # houses point at their woman (+30); the women records are at WOMEN
WOMEN, WOMEN_COUNT = 0x4562C, 20
MONGOL_COUNTRIES = 14
PLACE_NAMES = 0x48DD2                    # 2 x 33 x 15 bytes (Mongolia, world)
PLACE_X, PLACE_Y = 0x48D4E, 0x48D6F      # 2 x (33 x, 33 y) bytes, 0x42 apart: label positions on the map

# Faces: 40x48 = 5x6 4bpp tiles row-major (960 bytes), drawn by $7752 (persons) / $77CC (women). Code bit 15
# clear: portrait n = code (women: code + WOMAN_PORTRAIT), PORTRAITS[n] is a compressed 960-byte image ($7700).
# Bit 15 set: composed face ($73FE), see face_tiles. Both use palette line 1 = FACE_PALETTE.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAITS, PORTRAIT_COUNT = 0x7D272, 97
WOMAN_PORTRAIT = 0x39
FACE_PALETTE = 0x475DA                   # 16 MD colours
HEAD_LAYOUT = 0x46E74                    # 8 groups x 7 heads x word: layout number
LAYOUTS = 0x46EE4                        # 22 layouts x 5 parts x (first tile, tile count) words
PART_TILES = 0x47662                     # 8 groups x 7 heads x 2 versions x 5 parts x long pointer (raw tiles)
PART_NAMES = ["eyes", "nose", "mouth", "top", "body"]
PART_BITS = [6, 5, 4, 8, 7]              # code bit choosing version 1 of each part ($7372 fields 0-4)
DRAW_ORDER = [3, 4, 0, 1, 2]             # $73FE copies top, body, eyes, nose, mouth
MD_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def load(path: str = DEFAULT_ROM) -> bytes:
    return load_rom(path)


def be16(b: bytes, a: int) -> int:
    return b[a] << 8 | b[a + 1]


def be32(b: bytes, a: int) -> int:
    return int.from_bytes(b[a:a + 4], "big")


def text(b: bytes) -> str:
    s = b.split(b"\0")[0].decode("latin-1")
    return "".join(GLYPHS.get(c, c) for c in s)


def md_rgb(w: int) -> tuple[int, int, int]:
    return MD_LEVELS[w >> 1 & 7], MD_LEVELS[w >> 5 & 7], MD_LEVELS[w >> 9 & 7]


# --- scenarios ---------------------------------------------------------------------------------------------

def block_a(rom: bytes, n: int) -> bytes:
    a = be32(rom, SCENARIO_A + 4 * n)
    return rom[a:a + A_SIZE]


def block_b(rom: bytes, n: int) -> bytes:
    a = be32(rom, SCENARIO_B + 4 * n)
    return rom[a:a + B_SIZE]


def year(rom: bytes, n: int) -> int:
    return be16(block_b(rom, n), YEAR_AT)


def person(rec: bytes) -> dict:
    """24-byte person record (SFC +16.. shifted to +13..)."""
    return {
        "name": text(rec[:13]),
        "house": rec[13],                # 0xFF = none
        "country": rec[14],
        "hp": rec[15] >> 4, "hp_max": rec[15] & 15,
        "war": rec[16] >> 4, "pol": rec[16] & 15,      # 0-4 = E-A
        "cha": rec[17] >> 4, "lead": rec[17] & 15,
        "age": rec[18] - 256 if rec[18] > 127 else rec[18],
        "culture": rec[19] >> 2 & 7,     # bits 2-4 (SFC +22; inferred)
        "flags": rec[19] & 0xE3,
        "status": rec[20],               # 3 = king, 0x80 = empty slot
        "b21": rec[21],
        "face": be16(rec, 22),
    }


def persons(rom: bytes, n: int) -> list[dict]:
    """Used person slots of scenario n, with their slot number."""
    a = block_a(rom, n)
    out = []
    for k in range(PERSON_SLOTS):
        rec = a[PERSONS_AT + PERSON_SIZE * k:PERSONS_AT + PERSON_SIZE * (k + 1)]
        if rec[20] != 0x80 and rec[0] and k not in LOADER_EMPTIES.get(n, []):
            out.append({"slot": k, **person(rec)})
    return out


def families(rom: bytes, n: int) -> list[dict]:
    """The family blocks of scenario n: {house, persons, children} for each house the player can choose."""
    out = []
    for k in range(6):
        p = be32(rom, FAMILIES + 24 * n + 4 * k)
        if not p:
            continue
        rows = []
        for j in range(FAMILY_SLOTS):
            rec = rom[p + PERSON_SIZE * j:p + PERSON_SIZE * (j + 1)]
            if rec[0] and rec[20] != 0x80:
                rows.append({"slot": j, **person(rec)})
        kids = []
        for j in range(CHILD_SLOTS):
            rec = rom[p + CHILDREN_AT + CHILD_SIZE * j:p + CHILDREN_AT + CHILD_SIZE * (j + 1)]
            if not rec[0]:
                break
            kids.append({"name": text(rec[:13]), "raw": rec[13:].hex(" "), "face": be16(rec, 18)})
        out.append({"house": rom[FAMILY_HOUSES + 6 * n + k], "address": p, "persons": rows, "children": kids})
    return out


def countries(rom: bytes, n: int) -> list[dict]:
    a = block_a(rom, n)
    out = []
    for k in range(MONGOL_COUNTRIES if n == 0 else COUNTRY_SLOTS):
        r = a[COUNTRIES_AT + COUNTRY_SIZE * k:COUNTRIES_AT + COUNTRY_SIZE * (k + 1)]
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
    a = block_a(rom, n)
    out = []
    for k in range(HOUSE_SLOTS):
        r = a[HOUSES_AT + HOUSE_SIZE * k:HOUSES_AT + HOUSE_SIZE * (k + 1)]
        if not r[0]:
            continue
        first, king, woman = be32(r, 22), be32(r, 26), be32(r, 30)
        out.append({
            "id": k, "name": text(r[:22]),
            "first_country": (first - 0xFF0000 - COUNTRIES_AT) // COUNTRY_SIZE if first else None,
            "king": (king - 0xFF0000 - PERSONS_AT) // PERSON_SIZE if king else None,
            "woman": (woman - WOMEN) // WOMAN_SIZE if woman else None,
            "culture": r[34], "b35": r[35],
        })
    return out


def women(rom: bytes) -> list[dict]:
    out = []
    for k in range(WOMEN_COUNT):
        r = rom[WOMEN + WOMAN_SIZE * k:WOMEN + WOMAN_SIZE * (k + 1)]
        out.append({"id": k, "name": text(r[:13]), "b13": r[13], "b14": r[14], "country": r[15],
                    "face": be16(r, 16)})
    return out


def place_names(rom: bytes, world: bool) -> list[str]:
    a = PLACE_NAMES + 0x1EF * world
    return [text(rom[a + 15 * k:a + 15 * k + 15]) for k in range(33)]


def place_pos(rom: bytes, world: bool) -> list[tuple[int, int]]:
    x, y = PLACE_X + 0x42 * world, PLACE_Y + 0x42 * world
    return [(rom[x + k], rom[y + k]) for k in range(33)]


# --- faces -------------------------------------------------------------------------------------------------

_MASK = [(1 << k) - 1 for k in range(17)]


def decompress(rom: bytes, src: int) -> bytes:
    """The decompressor at $33F0: a flag byte per 8 items, MSB first; set = literal byte, clear = copy. The copy
    length and distance are prefix codes read from a 16-bit window over a bit stream of little-endian words
    (bit reader $3376); the flag and literal bytes are read from the same pointer between the words."""
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
    return decompress(rom, be32(rom, PORTRAITS + 4 * n))


def face_fields(code: int) -> dict:
    """$7372: group = bits 12-14, head type = bits 9-11 mod 7, part versions from PART_BITS."""
    g, m = code >> 12 & 7, (code >> 9 & 7) % 7
    return {"group": g, "type": m, "head": 7 * g + m, "variants": [code >> b & 1 for b in PART_BITS]}


def head_parts(rom: bytes, head: int) -> list[dict]:
    """The 5 parts of head 7 * group + type: face tiles covered and the two versions' source addresses."""
    g, m = divmod(head, 7)
    lay = be16(rom, HEAD_LAYOUT + 2 * head)
    out = []
    for k in range(5):
        first, count = be16(rom, LAYOUTS + 20 * lay + 4 * k), be16(rom, LAYOUTS + 20 * lay + 4 * k + 2)
        src = [be32(rom, PART_TILES + 0x118 * g + 4 * (v * 5 + m * 10 + k)) for v in range(2)]
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
    return [md_rgb(be16(rom, FACE_PALETTE + 2 * i)) for i in range(16)]
