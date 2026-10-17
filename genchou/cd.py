"""Mega-CD 蒼き狼と白き牝鹿・元朝秘史 (KOEI, 1993-09-24, GM T-76054): the cartridge program moved to the sub CPU,
plus the scenario 源平の争乱 (1180) and 21 portraits. See docs/MEGACD.md.

load() builds an image of the sub CPU's PRG-RAM (SMAIN.PRG at $C000, INIT.PRG at $66000) with GH2GRP.DAT's face
slots appended at FACE_SLOTS and the disc serial at 0x180, so rom.py's record decoders read it with
rom.LAYOUTS["C"]. Scenario n here is the CD menu order: 0 モンゴル高原の統一, 1 源平の争乱 (new), 2-4 = the
cartridge's 1-3 (cartridge scenario k is SCENARIOS[k]).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import megacd
import rom as R

DEFAULT_IMAGE = os.path.join(REPO, "roms", "megacd", "Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).7z")
SMAIN_AT, INIT_AT = 0xC000, 0x66000
FACE_SLOTS = 0x100000          # GH2GRP.DAT + 0x11A800 in the image: 1024-byte slots (960 bytes of tiles, 64 zero)
FACE_FILE_AT = 0x11A800
SLOT = 1024
SCENARIO_COUNT = 5
GENPEI = 1                     # the scenario only the CD has
SCENARIOS = [0, 2, 3, 4]       # CD scenario of cartridge scenario k
PORTRAIT_COUNT = 118           # slots 0-73 men (57-73 new), 74-117 women (114-117 new)
WOMAN_PORTRAIT = 0x4A          # women's code + 0x4A ($12ACE; cartridge + 0x39)
COMPOSED = 118                 # slot of composed face code c: COMPOSED + 32 * head + (c >> 4 & 31)
NEW_MEN = range(57, 74)
NEW_WOMEN = range(114, 118)


def load(path: str = DEFAULT_IMAGE) -> bytes:
    iso = megacd.data_track(path)
    fs = megacd.files(iso)
    img = bytearray(FACE_SLOTS)
    for name, at in (("SMAIN.PRG", SMAIN_AT), ("INIT.PRG", INIT_AT)):
        d = megacd.read(iso, fs[name])
        img[at:at + len(d)] = d
    img[0x180:0x180 + len(R.LAYOUTS["C"].serial)] = R.LAYOUTS["C"].serial
    return bytes(img) + megacd.read(iso, fs["GH2GRP.DAT"])[FACE_FILE_AT:]


def slot(img: bytes, n: int) -> bytes:
    return img[FACE_SLOTS + SLOT * n:FACE_SLOTS + SLOT * n + R.FACE_BYTES]


def face_slot(code: int, woman: bool = False) -> int:
    """The slot the game shows for a face code (verify_cd_faces.py)."""
    if not code & 0x8000:
        return code + (WOMAN_PORTRAIT if woman else 0)
    return COMPOSED + 32 * R.face_fields(code)["head"] + (code >> 4 & 31)


def face_tiles(img: bytes, code: int, woman: bool = False) -> bytes:
    return slot(img, face_slot(code, woman))
