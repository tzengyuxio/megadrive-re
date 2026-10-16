#!/usr/bin/env python3
"""Verify the 1775 scenario against the game: MAME picks "Start New Game" and goes on to "Select side."; an exec
hook at $9810 (right after $97EC copies the scenario with memcpy $5F1E) dumps RAM $FF000A..$FF16BA, which must equal
rom.scenario_image().

Usage: .venv/bin/python dokuritsu/verify_scenarios.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as L
from drive import schedule
from mame import run
from verify_faces import BOOT

HOOK = 0x9810


def main() -> None:
    rom = L.Rom()
    events, end = schedule((BOOT + " c:20 w300").split())
    rows = ",".join(f'{{{fr},"{k}","{v}"}}' for fr, k, v in events)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "sc")
        lua = f"""
local ev={{{rows}}}
local n=0
on_exec(0x{HOOK:X}, function()
  n=n+1
  local t={{}}
  for i=0,{L.SCENARIO_SIZE - 1} do t[#t+1]=string.char(rd8(0xFF0000+{L.SCENARIO_RAM}+i)) end
  local fh=io.open("{out}"..n, "wb"); fh:write(table.concat(t)); fh:close()
end)
on_frame(function(f)
  for _,e in ipairs(ev) do if e[1]==f then press(e[3], e[2]=="press") end end
  if f=={end} then quit() end
end)
"""
        run(rom.path, lua, debug=True)
        dumps = sorted(f for f in os.listdir(tmp) if f.startswith("sc"))
        if not dumps:
            print("hook not reached")
            sys.exit(1)
        with open(os.path.join(tmp, dumps[0]), "rb") as fh:
            got = fh.read()
    want = rom.scenario_image()
    same = sum(a == b for a, b in zip(got, want))
    print(f"scenario copy ({len(dumps)} call(s) of $97EC): {same}/{len(want)} bytes equal")
    ok = got == want
    print("ALL OK" if ok else "DIFFERENT")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
