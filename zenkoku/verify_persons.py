#!/usr/bin/env python3
"""Verify the daimyo and province fields against the game: at the first command screen of scenario 2 (織田信長,
尾張), write a daimyo record into slot 24 (age and the 5 abilities) and a province record into province 24, open
その他 → 情報 → 自国 and read the 18 numbers back from plane A (digit d = tiles $60 + 2d / $61 + 2d).
Every daimyo and province record of the 4 scenarios is shown once (daimyo k with province k), plus 2 rounds with a
different value in every field so that the field order is pinned down.

Usage: .venv/bin/python zenkoku/verify_persons.py [--rom ROM]   # Japan (default) or USA ROM
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as Z
from replay import replay
from verify_faces import SCENARIO2

# 姓名変更 No → ability screen (C x4) → 担当する大名はこれでよろしいですか Yes → CPU strength → 全てよろしいですか Yes
# → the computer daimyo move until 織田様、ご命令を (the USA version takes about twice as long as the Japanese)
FIRST_TURN = SCENARIO2 + (" b:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w600 c:10 w600 c:10 w600 w1200 c:10 w300"
                          " c:10 w300 c:10 w300 w15000")
INFO = "right:6 w30 right:6 w30 right:6 w60 c:20 w200 c:20 w300 down:6 w40 c:20 w300"  # その他 → 情報 → 自国
SLOT = PROVINCE = 24
PLANE_A, WIDTH = 0xE000, 32
# (row, column of the last digit) of each number
DAIMYO_POS = [(8, 29), (10, 29), (12, 29), (14, 29), (16, 29), (18, 29)]  # 年齢 健康 野心 運 魅力 知力
PROVINCE_POS = {"Soldiers": (12, 8), "Soldier_Loyalty": (14, 8), "Arms": (16, 8), "Training": (18, 8),
                "Gold": (12, 15), "Rice": (14, 15), "Loyalty": (16, 15), "Wealth": (18, 15),
                "Town": (12, 22), "Flood": (14, 22), "Kokudaka": (16, 22), "Debt": (18, 22)}


def number_at(nt: bytes, row: int, col: int) -> int | None:
    digits = ""
    while col >= 0:
        t = (nt[(row * WIDTH + col) * 2] << 8 | nt[(row * WIDTH + col) * 2 + 1]) & 0x7FF
        if not (0x60 <= t <= 0x72 and t % 2 == 0):
            break
        digits = str((t - 0x60) // 2) + digits
        col -= 1
    return int(digits) if digits else None


def main() -> None:
    ap = argparse.ArgumentParser(description="大名與國欄位的模擬器驗證（情報畫面）")
    ap.add_argument("--rom", default=Z.DEFAULT_ROM)
    args = ap.parse_args()
    rom = Z.Rom(args.rom)
    daimyo, provinces = [], []
    for s in range(Z.SCENARIO_COUNT):
        img = rom.scenario_image(s)
        daimyo += [(f"{s + 1}/{d['index']} {d['name']}", img[Z.DAIMYO_RAM + Z.DAIMYO_SIZE * d["index"]:][:6])
                   for d in rom.daimyos(s)]
        provinces += [(f"{s + 1}/{p} {name}", img[rom.L.provinces_ram + Z.PROVINCE_SIZE * p:][:Z.PROVINCE_SIZE])
                      for p, name in enumerate(rom.province_names(s))]
    # two rounds of made-up values, all different
    for k in range(2):
        daimyo.append((f"custom {k}", bytes(11 + 13 * i + k for i in range(6))))
        provinces.append((f"custom {k}", b"".join((101 + 37 * i + 5 * k).to_bytes(2, "big") for i in range(13))))
    n = max(len(daimyo), len(provinces))
    runs = []
    for i in range(n):
        d, p = daimyo[i % len(daimyo)][1], provinces[i % len(provinces)][1]
        ram = [(0xFF0000 + Z.DAIMYO_RAM + Z.DAIMYO_SIZE * SLOT, d),
               (0xFF0000 + rom.L.provinces_ram + Z.PROVINCE_SIZE * PROVINCE, p)]
        runs.append({"ram": ram, "steps": INFO, "at": 1250, "read": [("vram", PLANE_A, 28 * WIDTH * 2)]})
    results = replay(args.rom, FIRST_TURN, runs)
    bad_d, bad_p = set(), set()
    for i, res in enumerate(results):
        nt = res["read"][0]
        (dn, d), (pn, p) = daimyo[i % len(daimyo)], provinces[i % len(provinces)]
        if [number_at(nt, *pos) for pos in DAIMYO_POS] != list(d):
            bad_d.add(dn)
        want = {k: Z.be16(p, 2 * j) for j, (k, _) in enumerate(Z.PROVINCE_FIELDS)}
        got = {k: number_at(nt, *pos) for k, pos in PROVINCE_POS.items()}
        if any(got[k] != want[k] for k in got):
            bad_p.add(pn)
            if len(bad_p) <= 3:
                print("  ", pn, {k: (got[k], want[k]) for k in got if got[k] != want[k]})
    print(f"daimyo {len(daimyo) - len(bad_d)}/{len(daimyo)}: age + 5 abilities match")
    print(f"provinces {len(provinces) - len(bad_p)}/{len(provinces)}: 12 values match")
    for b in sorted(bad_d)[:10] + sorted(bad_p)[:10]:
        print("  NG " + b)
    sys.exit(1 if bad_d or bad_p else 0)


if __name__ == "__main__":
    main()
