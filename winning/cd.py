"""Mega-CD ウイニングポスト (KOEI, 1993, GM T-76044): the people (trainers, jockeys, owners, person names) and the
faces (portraits, composed faces, palettes). See docs/DISC_FORMAT.md.

The program is SMAIN.PRG on the sub CPU (PRG-RAM $C000); the tables are those of the SFC version
(~/works/superfamicom-re/winning), big-endian and padded. ORGKAO.DAT holds the faces uncompressed in MD tile format.
"""
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import megacd

DEFAULT_IMAGE = os.path.join(REPO, "roms", "megacd", "Winning Post (Japan).7z")
SMAIN_AT = 0xC000              # PRG-RAM address of SMAIN.PRG; its pointers are PRG-RAM addresses

# SMAIN.PRG offsets
SURNAME = 0x56274              # 256 x BE32 pointers: person surname
GIVEN = 0x55E74                # 256 x BE32 pointers: person given name
OWNER = 0x43F56                # 41 x 24
TRAINER = 0x4432E              # 30 x 22
PART_RUNS = 0x43A44            # 8 types x 6 bytes: 零件A and 零件B runs (first cell, width, rows), $18A6E
# SNDAT.DAT offsets
JOCKEY_A = 0x760               # 20 x 24: jockeys 0-19 (foreign, then 10 Japanese)
JOCKEY_B = 0x2B0               # 50 x 24: jockeys 20-69

PERSON_COUNT = 256
OWNER_COUNT, TRAINER_COUNT, JOCKEY_COUNT = 41, 30, 70

# ---------------------------------------------------------------- faces
# 40 x 48 = 5 x 6 MD tiles row-major (960 bytes). ORGKAO.DAT: portraits 0x00-0xCF in 1024-byte slots, then the
# composed faces' part sheets (8 types x 4 versions x 960 bytes) from slot 208 and their pointer table at slot 238.
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
SLOT = 1024
PORTRAIT_COUNT = 208
SECRETARY_FACE = 0xCF
SHEETS = 208 * SLOT
TYPES = 8
# The 6 face palettes in the SFC version's order (0-1 composed faces, 2-5 portraits): SMAIN.PRG offsets
# ($18BAC picks $4EF84 / $4EFA4 / $4EEE4 / $4EF04 / $4EF24 / $4EF44)
PALETTES = [0x42F84, 0x42FA4, 0x42EE4, 0x42F04, 0x42F24, 0x42F44]
LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)  # MAME's levels of the 3-bit MD colour values


def portrait_palette(code: int) -> int:
    """$18BAC: palette number (0-5) of portrait code 0x00-0xCF. The secretary (loaded once by $F194, not drawn by
    $18C6A) uses palette 3 in her dialogs."""
    if code == SECRETARY_FACE:
        return 3
    if code < 0x28 or code > 0xC4:
        return 4
    if code < 0x9D:
        return 2
    return 5 if 0xA8 <= code <= 0xB5 else 3


def composite_fields(code: int) -> dict:
    """$18A6E: type (bits 14-12) and the 4 part numbers (bits 1-0, 3-2, 5-4, 9-8) of a composed face code."""
    return {"type": code >> 12 & 7, "parts": [code & 3, code >> 2 & 3, code >> 4 & 3, code >> 8 & 3]}


def md_rgb(w: int) -> tuple[int, int, int]:
    return tuple(LEVELS[w >> s & 7] for s in (1, 5, 9))


def decode_tile(b: bytes) -> list[int]:
    """One 8x8 MD tile (4 bits per pixel, high nibble first) -> 64 colour indices, row-major."""
    return [b[i // 2] >> (4 if i % 2 == 0 else 0) & 15 for i in range(64)]


def tiles_pixels(data: bytes) -> list[int]:
    """30 tiles (5 x 6) -> 40 x 48 colour indices, row-major."""
    w = FACE_W * 8
    px = [0] * (w * FACE_H * 8)
    for t in range(FACE_W * FACE_H):
        tile = decode_tile(data[32 * t:32 * t + 32])
        tx, ty = t % FACE_W * 8, t // FACE_W * 8
        for i, v in enumerate(tile):
            px[(ty + i // 8) * w + tx + i % 8] = v
    return px


def text(b: bytes) -> str:
    """Shift-JIS; ESC K / ESC H switch half-width kana to katakana / hiragana (hiragana by default); 0 ends."""
    out, i, kata = [], 0, False
    while i < len(b) and b[i]:
        c = b[i]
        if c == 0x1B:
            kata = b[i + 1] == 0x4B
            i += 2
        elif 0x81 <= c < 0xA0 or 0xE0 <= c < 0xF0:
            out.append(b[i:i + 2].decode("cp932"))
            i += 2
        else:
            ch = unicodedata.normalize("NFKC", bytes([c]).decode("cp932"))
            if not kata and "ァ" <= ch <= "ヶ":
                ch = chr(ord(ch) - 0x60)
            out.append(ch)
            i += 1
    return unicodedata.normalize("NFC", "".join(out)).rstrip("　 ")


class Disc:
    def __init__(self, path: str = DEFAULT_IMAGE):
        self.path = path
        self.track01, self.sha1 = megacd.track01_sha1(path)
        iso = megacd.data_track(path)
        fs = megacd.files(iso)
        self.smain = megacd.read(iso, fs["SMAIN.PRG"])
        self.sndat = megacd.read(iso, fs["SNDAT.DAT"])
        self.kao = megacd.read(iso, fs["ORGKAO.DAT"])

    def u16(self, o: int) -> int:
        return self.smain[o] << 8 | self.smain[o + 1]

    def ptr(self, o: int) -> int:
        """BE32 PRG-RAM pointer at SMAIN offset o -> SMAIN offset."""
        return int.from_bytes(self.smain[o:o + 4], "big") - SMAIN_AT

    def string(self, o: int, n: int = 64) -> str:
        return text(self.smain[o:o + n])

    # ------------------------------------------------------------ people
    def person(self, i: int) -> tuple[str, str]:
        return self.string(self.ptr(SURNAME + 4 * i)), self.string(self.ptr(GIVEN + 4 * i))

    def owners(self) -> list[dict]:
        out = []
        for i in range(OWNER_COUNT):
            o = OWNER + 24 * i
            out.append({"index": i, "face": self.u16(o), "surname": self.string(o + 5, 7),
                        "given": self.string(o + 12, 7)})
        return out

    def trainers(self) -> list[dict]:
        out = []
        for i in range(TRAINER_COUNT):
            o = TRAINER + 22 * i
            out.append({"index": i, "face": self.u16(o), "jockey": 20 + self.smain[o + 2],
                        "surname": self.string(o + 8, 7), "given": self.string(o + 15, 7)})
        return out

    def jockey_record(self, i: int) -> bytes:
        o = JOCKEY_A + 24 * i if i < 20 else JOCKEY_B + 24 * (i - 20)
        return self.sndat[o:o + 24]

    def jockeys(self) -> list[dict]:
        """The SFC version's 22-byte records with 2 pad bytes (+15, +19); the person at +23."""
        out = []
        for i in range(JOCKEY_COUNT):
            r = self.jockey_record(i)
            s, g = self.person(r[23])
            out.append({"index": i, "face": r[0] << 8 | r[1], "person": r[23], "surname": s, "given": g})
        return out

    # ------------------------------------------------------------ faces
    def palette(self, n: int) -> list[int]:
        """MD colour words of face palette n (0-5)."""
        return [self.u16(PALETTES[n] + 2 * i) for i in range(16)]

    def portrait_bytes(self, code: int) -> bytes:
        return self.kao[SLOT * code:SLOT * code + FACE_BYTES]

    def sheet_face(self, t: int, v: int) -> bytes:
        """Version v (0-3) of type t's part sheet: a whole face whose cells the parts copy."""
        o = SHEETS + (4 * t + v) * FACE_BYTES
        return self.kao[o:o + FACE_BYTES]

    def part_cells(self, t: int) -> list[list[int]]:
        """$18A6E: the cells each slot copies: 0-14 from part 0 (上半), 15-29 from part 1 (下半), then a run of
        rows from part 2 (零件A) and one from part 3 (零件B), (first cell, width, rows) at PART_RUNS."""
        r = self.smain[PART_RUNS + 6 * t:PART_RUNS + 6 * t + 6]
        runs = [[r[k] + FACE_W * y + x for y in range(r[k + 2]) for x in range(r[k + 1])] for k in (0, 3)]
        return [list(range(15)), list(range(15, 30)), *runs]

    def composite_bytes(self, code: int) -> bytes:
        f = composite_fields(code)
        buf = bytearray(FACE_BYTES)
        for slot, cells in enumerate(self.part_cells(f["type"])):
            src = self.sheet_face(f["type"], f["parts"][slot])
            for c in cells:
                buf[32 * c:32 * c + 32] = src[32 * c:32 * c + 32]
        return bytes(buf)

    def face_bytes(self, code: int) -> bytes:
        return self.portrait_bytes(code) if code < PORTRAIT_COUNT else self.composite_bytes(code)

    def face_palette_number(self, code: int) -> int:
        if code < PORTRAIT_COUNT:
            return portrait_palette(code)
        return 0 if composite_fields(code)["type"] < 4 else 1

    def face_rgb(self, code: int) -> list[list[tuple[int, int, int]]]:
        pal = [md_rgb(c) for c in self.palette(self.face_palette_number(code))]
        px = tiles_pixels(self.face_bytes(code))
        w = FACE_W * 8
        return [[pal[v] for v in px[y * w:(y + 1) * w]] for y in range(FACE_H * 8)]
