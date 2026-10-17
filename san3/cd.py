"""Mega-CD 三國志III (KOEI, 1993, GM T-76014): the cartridge program on the sub CPU, plus the scenario 黄巾の乱
(184) and faces stored uncompressed with the composites pre-rendered. See docs/MEGACD.md.

Disc reads the disc's SMAIN.PRG (sub CPU PRG-RAM $C000), ORGKAO.DAT (faces) and SINARIO.DAT (scenarios). The
person records and the face palettes are the cartridge's formats at other addresses; Disc subclasses rom.Rom (with
those addresses) so the cartridge decoders read them. Scenario n here is the CD menu order: 0 黄巾の乱 (new), 1-6 =
the cartridge's 0-5.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import megacd
import rom as R

DEFAULT_IMAGE = os.path.join(REPO, "roms", "megacd", "Sangokushi III (Japan).7z")
SMAIN_AT = 0xC000              # PRG-RAM address of SMAIN.PRG
PERSONS = 0x3421E              # in SMAIN.PRG: 532 x 30 bytes, the cartridge's PERSONS
FACE_PAL_NO = 0x3ABCE          # the cartridge's FACE_PAL_NO / FACE_PALETTES
FACE_PALETTES = 0x3AFB2
COMPOSED_CODES = 0x3B8F0       # 311 composite face codes, ascending: code k is ORGKAO.DAT slot COMPOSED + k; a code
                               # not in the table shows slot COMPOSED (劉度's new D563: the table has his old D940)
COMPOSED_COUNT = 311
COMPOSED = R.FACE_COUNT        # slots 0-306 are plain faces 1-307
SLOT = 1024                    # ORGKAO.DAT: 960 bytes of tiles, 64 zero
SCENARIO_COUNT = 7
SCENARIO_SIZE = 0x1800         # SINARIO.DAT: 7 scenarios, the cartridge's 0-5 then 黄巾の乱
SCENARIO_PROVINCES = 0x84C     # after the 531 x 4 person bytes
HUANGJIN = 6                   # 黄巾の乱's block in SINARIO.DAT (menu scenario 0)
RAM = 0x78000                  # PRG-RAM address of the cartridge's work RAM layout ($FF0000)


class _Block(R.Rom):
    """One SINARIO.DAT block read with the cartridge's scenario decoders (as their scenario 0)."""
    def __init__(self, block: bytes):
        self.data = block

    def ptr(self, at: int) -> int:
        return {R.SCEN_PERSON_PTRS: 0, R.SCEN_PROVINCE_PTRS: SCENARIO_PROVINCES}[at]


class Disc(R.Rom):
    persons_at, face_pal_no, face_palettes = PERSONS, FACE_PAL_NO, FACE_PALETTES

    def __init__(self, path: str = DEFAULT_IMAGE):
        iso = megacd.data_track(path)
        fs = megacd.files(iso)
        self.data = megacd.read(iso, fs["SMAIN.PRG"])
        self.kao = megacd.read(iso, fs["ORGKAO.DAT"])
        self.sinario = megacd.read(iso, fs["SINARIO.DAT"])
        self.codes = [R.be16(self.data, COMPOSED_CODES + 2 * k) for k in range(COMPOSED_COUNT)]

    def scenario_block(self, n: int) -> bytes:
        """SINARIO.DAT block of menu scenario n."""
        k = HUANGJIN if n == 0 else n - 1
        return self.sinario[SCENARIO_SIZE * k:SCENARIO_SIZE * (k + 1)]

    def scenario_persons(self, n: int) -> list[dict]:
        return _Block(self.scenario_block(n)).scenario_persons(0)

    def scenario_provinces(self, n: int) -> list[dict]:
        return _Block(self.scenario_block(n)).scenario_provinces(0)

    def in_play(self, n: int) -> list[int]:
        """Person ids whose rank byte isn't FF in menu scenario n."""
        b = self.scenario_block(n)
        return [pid for pid in range(R.SCEN_PERSON_COUNT) if b[4 * pid + 1] != 0xFF]

    def face_slot(self, face: int) -> int:
        if not face & 0x8000:
            return face - 1
        return COMPOSED + (self.codes.index(face) if face in self.codes else 0)

    def slot(self, n: int) -> bytes:
        return self.kao[SLOT * n:SLOT * n + R.FACE_BYTES]

    def face_tiles(self, face: int) -> bytes:
        return self.slot(self.face_slot(face))
