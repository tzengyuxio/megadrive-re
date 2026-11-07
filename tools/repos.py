"""Paths outside this repo that a few scripts read, each overridable by an environment variable.

SFC_ORIGINAL: SFC ROMs (No-Intro zips) of the game library (default ~/game-library/_original/sfc); read by
    bushou/verify_maps.py and san2/tools/build_kanji_map.py instead of superfamicom-re's own roms/.
SUPERFAMICOM_RE: superfamicom-re checkout (default ~/works/superfamicom-re), for its decoder and kanji table;
    read by san2/tools/build_kanji_map.py.
"""
import os

SFC_ORIGINAL = os.path.expanduser(os.environ.get("SFC_ORIGINAL", "~/game-library/_original/sfc"))
SUPERFAMICOM_RE = os.path.expanduser(os.environ.get("SUPERFAMICOM_RE", "~/works/superfamicom-re"))
