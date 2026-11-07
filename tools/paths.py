"""Paths outside this repo (re-common §1, §11). The original files have one copy, in the game library:
~/game-library/_original/md/ (cartridge zips), _original/megacd/ (Mega-CD .7z images, bios/), _original/sfc/ (the
SFC ROMs bushou/verify_maps.py and san2/tools/build_kanji_map.py compare with). They are read only; anything
extracted from them goes to .emu/. GAME_LIBRARY overrides the library root, e.g. on another machine; a missing file
ends with a hint to copy it back from the backup instead of looking elsewhere.

SUPERFAMICOM_RE: superfamicom-re checkout (default ~/works/superfamicom-re), for the decoder and kanji table that
san2/tools/build_kanji_map.py reuses.
"""
import os
import sys

LIBRARY = os.environ.get("GAME_LIBRARY", os.path.expanduser("~/game-library"))
ORIGINAL = os.path.join(LIBRARY, "_original")
ORIGINAL_MD = os.path.join(ORIGINAL, "md")
ORIGINAL_MEGACD = os.path.join(ORIGINAL, "megacd")
ORIGINAL_SFC = os.path.join(ORIGINAL, "sfc")
SUPERFAMICOM_RE = os.path.expanduser(os.environ.get("SUPERFAMICOM_RE", "~/works/superfamicom-re"))


def _hint(kind, value, tb):
    sys.__excepthook__(kind, value, tb)
    if isinstance(value, FileNotFoundError) and str(value.filename or "").startswith(ORIGINAL):
        print(f"\n{os.path.basename(value.filename)} is not in {os.path.dirname(value.filename)}: copy it back from "
              "the backup (re-common §11), or set GAME_LIBRARY", file=sys.stderr)


sys.excepthook = _hint
