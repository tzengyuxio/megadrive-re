#!/usr/bin/env python3
"""Check rom.py's world map against the game's own map code, in MAME.

At the hero select a hook on $B408 (see verify_faces.py) calls the game's block expander $3C470(block, slot 0) for
every block 0-4049: it looks the block up in the row table, LZ-decodes it ($3C3E2 -> $3C5E) and writes the 24 x 24
cells to $FF75D4. The hook reads them back after each call and compares them with Rom.block_cells.

Usage: .venv/bin/python daikoukai2/verify_maps.py [--rom ROM] [--keep DIR]
"""
import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from drive import schedule
from mame import run
from verify_faces import HOOK, TO_HEROES

EXPAND, CELLS = 0x3C470, 0xFF75D4
BLOCKS = R.MAP_BLOCKS_W * R.MAP_BLOCKS_H
CELL_BYTES = 4 * R.MAP_BLOCK * R.MAP_BLOCK


def run_blocks(rom_path: str, out: str) -> None:
    events, end = schedule((TO_HEROES + " w9000").split())
    rows = ",".join(f'{{{f},"{k}","{v}"}}' for f, k, v in events)
    lua = f"""
local ev={{{rows}}}
on_frame(function(f) for _,e in ipairs(ev) do if e[1]==f then press(e[3], e[2]=="press") end end
  if f=={end} then print("NOHIT"); quit() end end)
local b=-1
local base=nil
local fh=io.open("{out}", "w")
on_exec({HOOK:#x}, function()
  if not base then base=REG("SP") end
  if b>=0 then
    local t={{string.format("%d ", b)}}
    for a={CELLS:#x},{CELLS + CELL_BYTES - 1:#x} do t[#t+1]=string.format("%02X", rd8(a)) end
    fh:write(table.concat(t), "\\n")
  end
  b=b+1
  if b>={BLOCKS} then fh:close(); print("DONE"); quit(); return end
  local sp=base-12    -- return address, block, slot
  SP:write_u32(sp, {HOOK:#x}); SP:write_u32(sp+4, b); SP:write_u32(sp+8, 0)
  SETREG("SP", sp); SETREG("PC", {EXPAND:#x})
end)
"""
    text = run(rom_path, lua, debug=True)
    if "DONE" not in text.split():
        raise RuntimeError("map code not reached\n" + text[-2000:])


def main() -> None:
    ap = argparse.ArgumentParser(description="世界地圖：遊戲自己展開的區塊 cell，對 rom.py 逐 byte 比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--keep", help="把模擬器輸出留在這個資料夾")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    with tempfile.TemporaryDirectory() as tmp:
        folder = args.keep or tmp
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "blocks.txt")
        run_blocks(args.rom, path)
        got = {}
        with open(path) as fh:
            for line in fh:
                b, data = line.split()
                got[int(b)] = bytes.fromhex(data)
    bad = [b for b in range(BLOCKS) if got.get(b) != rom.block_cells(b)]
    print(f"區塊 {BLOCKS - len(bad)}/{BLOCKS}：$3C470 寫出的 24 x 24 cell 與 rom.py 相同"
          + (f"（NG {bad[:10]}）" if bad else ""))
    print("OK" if not bad else "MISMATCH")
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
