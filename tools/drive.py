#!/usr/bin/env python3
"""Play an MD ROM in MAME (tools/mame.py) from a button script; save screenshots and memory dumps.

Steps (space separated):
  <button>[:hold][*n]  press for `hold` frames (default 4), then release for 20; n times
                       buttons: a b c start up down left right
  w<n>                 wait n frames
  @<tag>               screenshot → OUT_<tag>.png, and dumps OUT_<tag>.ram/.vram/.cram/.vsram/.regs with --dump-all
The script starts at frame 10. At the end OUT.png and OUT.ram / .vram / .cram / .vsram / .regs are written,
plus OUT_all.png (all screenshots side by side, half size).

--reads LO-HI traces CPU data reads (not opcode fetches) of that address range (hex, e.g. 0-FFFFF) during
--window START-END (frames) and prints one line per (PC, 256-byte page): count and address range, most frequent
first. --lua adds your own Lua (see the prelude API in tools/mame.py).

Usage: .venv/bin/python tools/drive.py ROM OUT "w900 start w200 a @menu" [--reads 0-FFFFF --window 900-1200]
"""
import argparse
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mame import run

READS_LUA = """
local st={}
local tap=nil
on_frame(function(f)
  if f==%(start)d then
    tap=SP:install_read_tap(%(lo)d, %(hi)d, "reads", function(off, data, mask)
      local pc=REG("CURPC")
      if off>=pc-16 and off<pc+16 then return end  -- opcode / operand / prefetch
      local key=string.format("%%06X %%04X", pc, off >> 8)
      local r=st[key]
      if not r then r={n=0,lo=off,hi=off}; st[key]=r end
      r.n=r.n+1; if off<r.lo then r.lo=off end; if off>r.hi then r.hi=off end
    end)
  end
  if f==%(end)d and tap then
    tap:remove()
    local keys={}
    for k,_ in pairs(st) do keys[#keys+1]=k end
    table.sort(keys, function(a,b) return st[a].n>st[b].n end)
    for i=1,math.min(#keys,400) do
      local r=st[keys[i]]
      print(string.format("READ pc=%%s n=%%d %%06X-%%06X", keys[i]:sub(1,6), r.n, r.lo, r.hi))
    end
  end
end)
"""


def schedule(steps: list[str]) -> tuple[list[tuple[int, str, str]], int]:
    """([(frame, press|release|shot, button or tag)], last frame)."""
    events, f = [], 10
    for st in steps:
        if st.startswith("w"):
            f += int(st[1:])
        elif st.startswith("@"):
            events.append((f, "shot", st[1:]))
            f += 1
        else:
            b, _, n = st.partition("*")
            b, _, hold = b.partition(":")
            for _ in range(int(n or 1)):
                events.append((f, "press", b))
                events.append((f + int(hold or 4), "release", b))
                f += int(hold or 4) + 20
    return events, f + 2


def events_lua(events: list[tuple[int, str, str]], out: str, end: int, dump_all: bool) -> str:
    rows = ",".join(f'{{{fr},"{k}","{v}"}}' for fr, k, v in events)
    return f"""
local ev={{{rows}}}
local OUT="{out}"
on_frame(function(f)
  for _,e in ipairs(ev) do
    if e[1]==f then
      if e[2]=="press" then press(e[3], true)
      elseif e[2]=="release" then press(e[3], false)
      else shot(OUT.."_"..e[3]..".png"); {'dump(OUT.."_"..e[3])' if dump_all else ''} end
    end
  end
  if f=={end} then shot(OUT..".png"); dump(OUT); quit() end
end)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="用按鍵序列操作遊戲，截圖並 dump 記憶體")
    ap.add_argument("rom")
    ap.add_argument("out", help="輸出檔名前綴")
    ap.add_argument("steps")
    ap.add_argument("--lua", help="額外的 Lua 檔")
    ap.add_argument("--reads", help="追蹤 CPU 讀取的位址範圍，如 0-FFFFF")
    ap.add_argument("--window", help="追蹤的幀範圍，如 900-1200（預設整段）")
    ap.add_argument("--dump-all", action="store_true", help="每個 @tag 也 dump 記憶體")
    ap.add_argument("--debug", action="store_true", help="開 MAME debugger（--lua 用到 on_exec 時）")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    events, end = schedule(args.steps.split())
    extra = ""
    if args.lua:
        with open(args.lua) as fh:
            extra = fh.read()
    if args.reads:
        lo, hi = (int(x, 16) for x in args.reads.split("-"))
        start, stop = (int(x) for x in args.window.split("-")) if args.window else (10, end - 1)
        extra += READS_LUA % {"lo": lo, "hi": hi, "start": start, "end": stop}
    text = run(args.rom, extra + events_lua(events, out, end, args.dump_all), debug=args.debug)
    tags = [v for _, k, v in events if k == "shot"]
    if tags:
        ims = [Image.open(f"{out}_{t}.png") for t in tags]
        ims = [im.resize((im.width // 2, im.height // 2)) for im in ims]
        sheet = Image.new("RGB", (sum(im.width for im in ims), max(im.height for im in ims)))
        x = 0
        for im in ims:
            sheet.paste(im, (x, 0))
            x += im.width
        sheet.save(f"{out}_all.png")
    lines = [line for line in text.splitlines() if not line.startswith(("Warning:", "Average speed"))]
    print(f"frames {end}, shots {len(tags)}")
    for line in lines[:60]:
        print(line)


if __name__ == "__main__":
    main()
