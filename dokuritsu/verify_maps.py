#!/usr/bin/env python3
"""Verify the strategy map decoding against the game: at the first Continental Congress, "Who will you ask for
support?" + A shows the North map ($DE70 with region 0); holding down moves the cursor south through the locations
and on to the Central and the South map. On each region k
- VRAM tiles 0x1C0.. (672) must be rom.map_raw(k), except colour 15 (white land) turned into 3 / 8 / 12 (the owner
  colouring);
- plane $F000 cells (2, 2)-(29, 25) must be rom.map_tilemap(), except the open-sea cells, which show the animated
  sea tiles 0x658 + ((x + 2 y) & 3) (palette 1); their positions come from a table not found yet, but their tiles
  are all colour 0 (one Central tile has a single stray pixel);
- CRAM line 1 must be rom.map_palette() except colours 9-11 (water, cycling).

Usage: .venv/bin/python dokuritsu/verify_maps.py
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as L
from replay import replay
from verify_faces import BOOT

# Select side → detail → Confirm C-in-C → Set Options → (START) settings OK? → Continental Congress … the budget,
# the regiments → "Who will you ask for support?"
CONGRESS = (BOOT + " c:20 w300 c:20 w300 c:20 w300 c:20 w300 start:20 w400 c:20 w600 c:20 w900"
            + " c:20 w400" * 5)
PLANE, SEA_TILE, WATER = 0xF000, 0x658, (9, 10, 11)
OWNER_COLOURS = {3, 8, 12}
REGION_STEPS = [("a:20 w400", 420), ("a:20 w400 down:120 w200", 740), ("a:20 w400 down:120 w200 down:200 w300", 1240)]


def main() -> None:
    rom = L.Rom()
    n = L.MAP_W * L.MAP_H
    runs = [{"steps": steps, "at": at, "read": [("vram", 32 * L.MAP_FIRST_TILE, 32 * n), ("vram", PLANE, 2048), ("cram", 32, 32)]}
            for steps, at in REGION_STEPS]
    tm, pal, failed = rom.map_tilemap(), rom.map_palette(), 0
    for k, res in enumerate(replay(rom.path, CONGRESS, runs)):
        vram, plane, cram = res["read"]
        raw = rom.map_raw(k)
        recolour, other = Counter(), 0
        for a, b in zip(vram, raw):
            for s in (4, 0):
                p, q = a >> s & 15, b >> s & 15
                if p != q:
                    if q == 15 and p in OWNER_COLOURS:
                        recolour[p] += 1
                    else:
                        other += 1
        cells_same = sea = sea_drawn = cells_bad = 0
        for i in range(n):
            x, y = i % L.MAP_W, i // L.MAP_W
            o = 2 * (32 * (y + 2) + x + 2)
            e = plane[o] << 8 | plane[o + 1]
            if e == tm[i]:
                cells_same += 1
            elif e == 0x2000 | SEA_TILE + ((x + 2 * y) & 3):
                sea += 1
                sea_drawn += raw[32 * i:32 * i + 32] != bytes(32)
            else:
                cells_bad += 1
        got_pal = [cram[2 * c] << 8 | cram[2 * c + 1] for c in range(16)]
        pal_bad = [c for c in range(16) if c not in WATER and got_pal[c] != pal[c]]
        ok = not other and not cells_bad and not pal_bad
        failed += not ok
        print(f"region {k} {L.REGIONS[k]}: tiles {sum(recolour.values())} px owner-coloured "
              f"({', '.join(f'15→{c}: {m}' for c, m in sorted(recolour.items()))}), {other} other px differ; "
              f"tilemap {cells_same}/{n} same + {sea} sea cells ({sea_drawn} not blank), {cells_bad} other; "
              f"palette {16 - len(WATER) - len(pal_bad)}/{16 - len(WATER)}" + ("" if ok else "  NG"))
    print("ALL OK" if not failed else f"{failed} region(s) differ")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
