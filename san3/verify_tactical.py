#!/usr/bin/env python3
"""Check rom.py's battlefields against the game's own battlefield loader $47F20.

$47F20 decompresses LZ stream TACTICAL_PTRS[$FF9014] to $FFCC04. Scenario 1 is played as 劉備 up to the
command menu; at the end of the first face load ($F466) the script sets $FF9014 = k, pushes $F466 as return
address and jumps to $47F20. When the loader returns to $F466 the 1342 bytes at $FFCC04 are saved and the next
k is called, for all 68 entries. Each must equal Rom.tactical_raw(k) (and its SFC counterpart, see rom.py).

Usage: .venv/bin/python san3/verify_tactical.py [--rom ROM]
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

TO_MENU = ("w1500 a:20 w200 start:30 w300 w20 w300 w20 w300 start:5 w300 c:10 w300 c:10 w300 up:6 w30 c:10 w300"
           " right:6 w30 right:6 w30 c:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w600 w600 w600"
           " c:10 w200 w600")
LOADER, INDEX, BUFFER = 0x47F20, 0xFF9014, 0xFFCC04
HOOK = 0xF466


def capture(rom_path: str, out: str) -> None:
    events, end = schedule(TO_MENU.split())
    rows = ",".join(f'{{{f},"{k}","{v}"}}' for f, k, v in events)
    lua = f"""
local ev={{{rows}}}
local k=-1
local fh=io.open("{out}", "w")
on_frame(function(f)
  for _,e in ipairs(ev) do if e[1]==f then press(e[3], e[2]=="press") end end
  if f=={end} then fh:close(); print("NOHIT"); quit() end
end)
on_exec({HOOK}, function()
  if k>=0 then
    local t={{}}
    for a={BUFFER},{BUFFER + R.TACTICAL_SIZE - 1} do t[#t+1]=string.format("%02X", rd8(a)) end
    fh:write(table.concat(t), "\\n")
  end
  k=k+1
  if k<{R.TACTICAL_COUNT} then
    wr8({INDEX}, k)
    local sp=REG("SP")-4
    SETREG("SP", sp)
    SP:write_u32(sp, {HOOK})
    SETREG("PC", {LOADER})
  else
    fh:close(); print("DONE"); quit()
  end
end)
"""
    text = run(rom_path, lua, debug=True)
    if "DONE" not in text.split():
        raise RuntimeError("face loader not reached")


def main() -> None:
    ap = argparse.ArgumentParser(description="戰場：遊戲自己的戰場載入程式對 rom.py 逐 byte 比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "fields.txt")
        capture(args.rom, path)
        with open(path) as fh:
            got = [bytes.fromhex(line.strip()) for line in fh]
    ok = sum(g == rom.tactical_raw(k) for k, g in enumerate(got))
    print(f"戰場：{ok}/{R.TACTICAL_COUNT} 筆與 rom.py 相同（遊戲 $47F20 解出的 {R.TACTICAL_SIZE} bytes）")
    good = ok == R.TACTICAL_COUNT == len(got)
    print("OK" if good else "MISMATCH")
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
