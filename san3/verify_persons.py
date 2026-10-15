#!/usr/bin/env python3
"""Check rom.py's person table against the game's own 武将一覧 screen, read back from screenshots.

Scenario 1 is played as 劉備 up to the command menu. Then the province's officer chain in RAM (劉備's record
+0 = next person, FFFF ends) is rewritten to 劉備 → persons 0-530 (except 劉備), each moved into the province
with 関羽's rank 軍師 (+0C rank, +10 province, +11 faction copied from 関羽). The list 情報 → 自国 → 武将一覧 then shows
all of them, 8 rows per page (down = next page); right switches the columns: 忠 仕 齢 兵士 / 知 政 武 魅 /
陸 水 訓 士. Each page is read off the screenshot with the game's own font (exact 16x16 / 8x16 masks) and
compared with rom.py: name, 齢 (= 189 - 生年 + 1, 0 if not born yet), 知 政 武 魅 and
陸 水 (this list shows the bare values; 徴兵's list adds the item bonus, e.g. 関羽 武力 98 + 5 = 103).

Usage: .venv/bin/python san3/verify_persons.py [--rom ROM] [--keep DIR]
"""
import argparse
import os
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from drive import schedule
from mame import run

TO_MENU = ("w1500 a:20 w200 start:30 w300 w20 w300 w20 w300 start:5 w300 c:10 w300 c:10 w300 up:6 w30 c:10 w300"
           " right:6 w30 right:6 w30 c:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w600 w600 w600"
           " c:10 w200")
# back to the top menu, 情報 (4th), 自国 (2nd), 武将一覧 (2nd)
TO_LIST = " b:10 w120 down:6 w30 down:6 w30 down:6 w30 c:10 w120 down:6 w30 c:10 w120 down:6 w30 c:10 w120"
PERSON_RAM = 0xFF1562
LIU_BEI, GUAN_YU = 481, 71
YEAR = 189
ROWS, ROW_Y, ROW_X0, ROW_X1 = 8, 32, 16, 240  # text area inside the frame
BG = (0, 52, 87)
COLUMNS = (("忠", "仕", "齢", "兵士"), ("知", "政", "武", "魅"), ("陸", "水", "訓", "士"))


class Reader:
    """Text of a screenshot row, matched against the game's glyphs (any colour other than the panel's)."""

    def __init__(self, rom: R.Rom):
        self.full = {}
        for i, code in enumerate(rom.font_codes()):
            mask = tuple(tuple(r) for r in rom.glyph(i))
            if any(any(r) for r in mask):
                self.full.setdefault(mask, rom.text(code.to_bytes(2, "big")))
        self.half = {}
        for c in list(range(0x21, 0x7F)) + list(range(0xA1, 0xE0)):
            at = R.FONT_HALF + 16 * (c - 0x20)
            mask = tuple(tuple(rom.data[at + y] >> (7 - x) & 1 for x in range(8)) for y in range(16))
            if any(any(r) for r in mask):
                self.half.setdefault(mask, bytes([c]).decode("cp932"))

    def row(self, im: Image.Image, y: int) -> str:
        px = im.load()
        on = [[int(px[x, y + dy] != BG) for x in range(ROW_X1)] for dy in range(16)]
        out, x = [], ROW_X0
        while x + 8 <= ROW_X1:
            cell = tuple(tuple(on[dy][x:x + 8]) for dy in range(16))
            if not any(any(r) for r in cell):
                out.append(" ")
                x += 8
                continue
            if x + 16 <= ROW_X1:
                wide = tuple(tuple(on[dy][x:x + 16]) for dy in range(16))
                if wide in self.full:
                    out.append(self.full[wide])
                    x += 16
                    continue
            out.append(self.half.get(cell, "?"))
            x += 8
        return "".join(out)


def steps_for(n_pages: int, n_cols: int) -> str:
    """Shoot every page of each column set: down through the pages, right (the page stays), up back, ..."""
    s = TO_MENU + TO_LIST
    for col in range(n_cols):
        pages = range(n_pages) if col % 2 == 0 else range(n_pages - 1, -1, -1)
        move = " down:6 w40" if col % 2 == 0 else " up:6 w40"
        s += move.join(f" w30 @c{col}p{page}" for page in pages)
        s += " right:6 w60"
    return s


def capture(rom_path: str, chain: list[int], folder: str, n_pages: int, n_cols: int = len(COLUMNS),
            patch: dict[int, bytes] | None = None) -> None:
    """Screenshots c<col>p<page>.png; patch = {file offset: bytes} written to the cartridge ROM first."""
    events, end = schedule(steps_for(n_pages, n_cols).split())
    rows = ",".join(f'{{{f},"{k}","{v}"}}' for f, k, v in events)
    first_list = schedule(TO_MENU.split())[1]
    ids = ",".join(str(p) for p in chain)
    lua = "".join(f'rom_write({o}, "{"".join(f"\\{b}" for b in data)}")\n' for o, data in (patch or {}).items())
    lua += f"""
local ev={{{rows}}}
local chain={{{ids}}}
on_frame(function(f)
  if f=={first_list} then
    local src={PERSON_RAM}+30*{GUAN_YU}
    for i=1,#chain do
      local a={PERSON_RAM}+30*chain[i]
      wr16(a, i<#chain and chain[i+1] or 0xFFFF)
      if i>1 then for _,k in ipairs({{0x0C,0x10,0x11}}) do wr8(a+k, rd8(src+k)) end end
    end
  end
  for _,e in ipairs(ev) do
    if e[1]==f then
      if e[2]=="press" then press(e[3], true)
      elseif e[2]=="release" then press(e[3], false)
      else shot("{folder}/"..e[3]..".png") end
    end
  end
  if f=={end} then quit() end
end)
"""
    run(rom_path, lua)


def expected(rom: R.Rom) -> dict[int, dict]:
    return {p["id"]: {"name": p["name"], "齢": max(YEAR - p["born"] + 1, 0), "知": p["int"], "政": p["pol"],
                      "武": p["war"], "魅": p["cha"], "陸": p["land"], "水": p["water"]} for p in rom.persons()}


def main() -> None:
    ap = argparse.ArgumentParser(description="人物表：武将一覧畫面（字型比對讀回）對 rom.py 逐欄比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--keep", help="把截圖留在這個資料夾")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    chain = [LIU_BEI] + [p for p in range(R.SCEN_PERSON_COUNT) if p != LIU_BEI]
    n_pages = -(-len(chain) // ROWS)
    want = expected(rom)
    reader = Reader(rom)
    with tempfile.TemporaryDirectory() as tmp:
        folder = args.keep or tmp
        os.makedirs(folder, exist_ok=True)
        capture(args.rom, chain, folder, n_pages)
        seen = {}
        for col, names in enumerate(COLUMNS):
            for page in range(n_pages):
                im = Image.open(os.path.join(folder, f"c{col}p{page}.png")).convert("RGB")
                for r in range(ROWS):
                    i = page * ROWS + r
                    if i >= len(chain):
                        break
                    words = reader.row(im, ROW_Y + 16 * r).split()
                    row = seen.setdefault(chain[i], {"name": words[0] if words else ""})
                    if row["name"] != (words[0] if words else ""):
                        row["name"] = "?"
                    row.update(zip(names, words[2:]))
    fields = ("name", "齢", "知", "政", "武", "魅", "陸", "水")
    bad = []
    for pid in chain:
        got = seen.get(pid, {})
        diff = [f for f in fields if str(got.get(f)) != str(want[pid][f])]
        if diff:
            bad.append((pid, diff, {f: got.get(f) for f in diff}, {f: want[pid][f] for f in diff}))
    print(f"人物（劇本 1 的 {len(chain)} 人，欄位 {' '.join(fields)}）：{len(chain) - len(bad)}/{len(chain)} 全同")
    for b in bad[:20]:
        print("  NG", *b)
    print("OK" if not bad else "MISMATCH")
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
