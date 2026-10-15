#!/usr/bin/env python3
"""Verify the city fields against the game: start scenario 4 as 曹操, open the C menu's 城市 map and move the
cursor onto 洛陽 (A shows its panel). Before that, 洛陽's record (city 10) gets the values of every city of the 7
scenarios in turn, plus 2 rounds of made-up values (all different). The panel (plane A, digit d = tile $7E0 + 2d)
must show 農 (+8), 商 (+14), 人口 (+C), 民忠 (+B), 治水度 (+A), 士兵數 (+4), 訓練 (+10) and 士氣 (+11).

Usage: .venv/bin/python sgz5/verify_cities.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from drive import schedule
from replay import replay
from verify_faces import number_at
from verify_persons import BOOT_MENU

TO_PANEL = "c:10 w100 down:6 w30 a:10 w100 left:6 w40 a:10 w100"  # C menu → 城市 → cursor onto 洛陽 → A
CITY = 10
# field: (record offset, size, row, last digit column)
FIELDS = {"農": (8, 2, 10, 8), "商": (0x14, 2, 10, 16), "人口": (0xC, 4, 14, 26), "民忠": (0xB, 1, 14, 36),
          "治水度": (0xA, 1, 19, 14), "士兵數": (4, 4, 22, 26), "訓練": (0x10, 1, 22, 31), "士氣": (0x11, 1, 22, 36)}


def main() -> None:
    rom = R.Rom()
    cities = []
    for s in range(R.SCENARIO_COUNT):
        img = rom.city_image(s)
        cities += [(f"{s + 1}/{c['id']} {c['name']}", img[R.CITY_SIZE * c["id"]:][:R.CITY_SIZE])
                   for c in rom.cities(s)]
    for k in range(2):
        rec = bytearray(rom.city_image(3)[R.CITY_SIZE * CITY:][:R.CITY_SIZE])
        for i, (off, size, _, _) in enumerate(FIELDS.values()):
            rec[off:off + size] = (11 + 7 * i + k if size == 1 else 1234 * (i + 1) + 10 * k).to_bytes(size, "big")
        cities.append((f"custom {k}", bytes(rec)))
    at = schedule(TO_PANEL.split())[1] - 20
    runs = [{"ram": [(0xFF0000 + R.CITY_RAM + R.CITY_SIZE * CITY + 2, rec[2:0x1A])], "steps": TO_PANEL, "at": at,
             "read": [("vram", 0xE000, 24 * 64 * 2)]} for _, rec in cities]
    bad = []
    for (label, rec), res in zip(cities, replay(R.DEFAULT_ROM, BOOT_MENU, runs)):
        nt = res["read"][0]
        diff = {}
        for f, (off, size, row, col) in FIELDS.items():
            want, got = int.from_bytes(rec[off:off + size], "big"), number_at(nt, row, col)
            if got != want:
                diff[f] = (got, want)
        if diff:
            bad.append(f"{label} {diff}")
    print(f"cities {len(cities) - len(bad)}/{len(cities)}: 8 numbers each read back from 洛陽's panel")
    for b in bad[:20]:
        print("  NG " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
