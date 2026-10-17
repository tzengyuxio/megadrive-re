"""Mega-CD 信長の野望・覇王伝 (KOEI, 1994, GM T-76024): the cartridge program on the sub CPU, plus the scenario
1583 and 28 portraits for persons who had composed faces. See docs/MEGACD.md.

Disc reads the disc's SMAIN.PRG (sub CPU PRG-RAM $C000: the face tables and palette), ORGKAO.DAT (portraits,
uncompressed), SAVEDAT1-4.DAT (the 4 scenarios' RAM images) and TAIKI.DAT (the later-appearing persons) and
subclasses rom.Rom with those, so the cartridge decoders read them. MONTAGE.DAT holds the cartridge's composite part
streams byte for byte, so composed faces come from the cartridge ROM (cart).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import megacd
import rom as R

DEFAULT_IMAGE = os.path.join(REPO, "roms", "megacd", "Nobunaga no Yabou - Haouden (Japan).7z")
SMAIN_AT = 0xC000              # PRG-RAM address of SMAIN.PRG
RAM = 0x78000                  # PRG-RAM address of the cartridge's work RAM layout ($FF0000)
FACE_TABLE = 0x419A4           # in SMAIN.PRG: the cartridge's FACE_TABLE / FACE_TABLE2 / FACE_PALETTE
FACE_TABLE2 = 0x41B02
FACE_PALETTE = 0x2DDF4
SLOT = 1024                    # ORGKAO.DAT: 960 bytes of tiles, 64 zero
PORTRAIT_COUNT = 376           # 0-347 the cartridge's, 348-375 new
NEW_PORTRAITS = range(R.PORTRAIT_COUNT, PORTRAIT_COUNT)
SCENARIO_COUNT = 4
SCENARIO_YEARS = [1551, 1568, 1582, 1583]
SCENARIO_FILES = ["SAVEDAT1.DAT", "SAVEDAT2.DAT", "SAVEDAT3.DAT", "SAVEDAT4.DAT"]  # RAM $FF0000-$FF7475


class Disc(R.Rom):
    scenario_count, face_table, face_table2, face_palette_at = SCENARIO_COUNT, FACE_TABLE, FACE_TABLE2, FACE_PALETTE

    def __init__(self, path: str = DEFAULT_IMAGE, cart: R.Rom | None = None):
        iso = megacd.data_track(path)
        fs = megacd.files(iso)
        self.data = megacd.read(iso, fs["SMAIN.PRG"])
        self.kao = megacd.read(iso, fs["ORGKAO.DAT"])
        self.images = [megacd.read(iso, fs[n]) for n in SCENARIO_FILES]
        self.taiki = megacd.read(iso, fs["TAIKI.DAT"])
        self.cart = cart or R.Rom()
        # TAIKI.DAT: one list per scenario, each ended by a record with an empty name
        self.future_at, p = [], 0
        for _ in range(SCENARIO_COUNT):
            self.future_at.append(p)
            while self.taiki[p + 4]:
                p += R.FUTURE_SIZE
            p += R.FUTURE_SIZE

    def image(self, sc: int) -> bytes:
        """The scenario's RAM image (its pointers are PRG-RAM addresses, RAM + offset, not $FFxxxx)."""
        return self.images[sc]

    def future_source(self, sc: int) -> tuple[bytes, int]:
        return self.taiki, self.future_at[sc]

    def portrait_tiles(self, n: int) -> bytes:
        return self.kao[SLOT * n:SLOT * n + R.FACE_BYTES]

    def composite(self, g: int, code: int) -> bytes:
        return self.cart.composite(g, code)
