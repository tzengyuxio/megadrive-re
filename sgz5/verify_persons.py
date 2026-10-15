#!/usr/bin/env python3
"""Verify the person fields against the game: start scenario 4 as 曹操 and open the C menu's 武將 list (all
officers in id order, 7 per page, rows 6, 8, ... 18; digit d = tile $7E0 + 2d on plane A). Before the list
opens, the records of the 7 officers on its first page get the values of other persons: every person of
scenario 4 once, plus 2 rounds of made-up values (all different) that pin down the field order. Pages 2-4 (C)
must show 武力 智力 政治 魅力 (+6..+9), 經驗值 威名 (+C, +E) and 氣力 忠誠 (+10, +11); 忠誠 101 (rulers, persons
not in service) is shown without a number.

Usage: .venv/bin/python sgz5/verify_persons.py
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
from verify_text import TO_MAP

# ruler-select map → 許昌 (one step down from the start) → 曹操 選擇 → 決定 (cursor to the bottom-right corner)
BOOT_MENU = (TO_MAP + " down:6 w40 a:10 w60 a:10 w60 " + "down:6 w20 " * 12 + "right:6 w20 " * 6 + "a:10 w200")
TO_LIST = "c:10 w100 a:10 w100"  # C menu → 武將
SCENARIO = 3
SLOTS = [3, 10, 11, 12, 13, 18, 20]  # 于禁 尹默 公孫度 公孫恭 公孫康 太史慈 孔融, the list's first page
ROWS = [6 + 2 * k for k in range(7)]
# page (C presses) -> [(field, last digit column)]
PAGES = {1: [("武力", 16), ("智力", 23), ("政治", 30), ("魅力", 36)], 2: [("經驗值", 18), ("威名", 26)],
         3: [("氣力", 16), ("忠誠", 30)]}


def fields(img: bytes, r: int) -> dict:
    be16 = lambda a: img[a] << 8 | img[a + 1]
    return {"武力": img[r + 6], "智力": img[r + 7], "政治": img[r + 8], "魅力": img[r + 9], "經驗值": be16(r + 0xC),
            "威名": be16(r + 0xE), "氣力": img[r + 0x10], "忠誠": img[r + 0x11]}


def main() -> None:
    rom = R.Rom()
    img = rom.person_image(SCENARIO)
    people = [(f"{p['id']} {p['name']}", img[R.PERSON_SIZE * p["id"]:][:R.PERSON_SIZE])
              for p in rom.persons(SCENARIO)]
    for k in range(2):  # made-up records: 4 abilities, exp, fame, 氣力, 忠誠 all different
        rec = bytearray(R.PERSON_SIZE)
        rec[6:10] = bytes(11 + 13 * i + k for i in range(4))
        rec[0xC:0x10] = (12345 + 1111 * k).to_bytes(2, "big") + (2345 + 111 * k).to_bytes(2, "big")
        rec[0x10], rec[0x11] = 77 + k, 55 + k
        people.append((f"custom {k}", bytes(rec)))
    groups = [people[i:i + len(SLOTS)] for i in range(0, len(people), len(SLOTS))]
    runs = []
    for g in groups:
        ram = [(0xFF0000 + R.PERSON_RAM + R.PERSON_SIZE * s + 6, rec[6:0x12]) for s, (_, rec) in zip(SLOTS, g)]
        for presses in PAGES:
            steps = TO_LIST + " c:10 w60" * presses
            runs.append({"ram": ram, "steps": steps, "at": schedule(steps.split())[1] - 20,
                         "read": [("vram", 0xE000, 20 * 64 * 2)]})
    results = iter(replay(R.DEFAULT_ROM, BOOT_MENU, runs))
    bad, n, dash = [], 0, 0
    for g in groups:
        got = {}
        for presses, cols in PAGES.items():
            nt = next(results)["read"][0]
            for row, (label, _) in zip(ROWS, g):
                for f, col in cols:
                    got[(label, f)] = number_at(nt, row, col)
        for label, rec in g:
            n += 1
            want = fields(rec, 0)
            diff = {f: (got[(label, f)], v) for f, v in want.items()
                    if got[(label, f)] != v and not (f == "忠誠" and v > 100 and got[(label, f)] is None)}
            dash += want["忠誠"] > 100
            if diff:
                bad.append(f"{label} {diff}")
    print(f"persons {n - len(bad)}/{n}: 8 numbers each (武力 智力 政治 魅力 經驗值 威名 氣力 忠誠) read back "
          f"({dash} with 忠誠 101, shown without a number)")
    for b in bad[:20]:
        print("  NG " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
