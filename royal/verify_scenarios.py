#!/usr/bin/env python3
"""Verify the scenario decoding against the game: pick each of the 4 scenarios in MAME (1 player), dump the RAM on
the house selection screen and compare the scenario block at SCENARIO_RAM with rom.scenario_block, except the
run-time pointer fields (header +0, person +0, province +0; 4 bytes each). Also checks that the menu shows the
decoded titles (screenshot only) and reports the persons / houses / provinces read back from RAM.

Usage: .venv/bin/python royal/verify_scenarios.py [--rom ROM] [--keep DIR]
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import rom as R
from drive import schedule
from mame import run

# power-on → intro (A skips) → title (START twice) → scenario menu
TITLE = "w600 a:10 w200 start:10 w200 c:10 w600 start:4 w100 start:4 w150 "


YEARS_RAM = R.SCENARIO_RAM + R.YEARS_AT  # the menu loads the scenario under the cursor (years 0, 5, 10, 15)


def scenario_lua(s: int, out: str) -> str:
    """Power-on → scenario menu (TITLE); press DOWN until the menu has loaded scenario s (single presses are
    sometimes missed), then C three times (scenario, its story, 1 player) → house selection screen; dump."""
    events, start = schedule(TITLE.split())
    rows = ",".join(f'{{{fr},"{k}","{v}"}}' for fr, k, v in events)
    return f"""
local ev={{{rows}}}
local t, phase = 0, "menu"
on_frame(function(f)
  for _,e in ipairs(ev) do if e[1]==f then press(e[3], e[2]=="press") end end
  if f<{start} then return end
  t=t+1
  if phase=="menu" then
    if t%60==1 then
      if rd8(0x{YEARS_RAM:X})=={5 * s} then phase="go"; t=0 else press("down", true) end
    elseif t%60==11 then press("down", false) end
  elseif phase=="go" then
    if t==100 or t==320 or t==540 then press("c", true) end
    if t==104 or t==324 or t==544 then press("c", false) end
    if t==760 then shot("{out}.png"); dump("{out}"); quit() end
  end
end)
"""


def pointer_offsets() -> set[int]:
    offs = set(range(4))
    for n in range(R.PERSON_COUNT):
        offs |= set(range(R.PERSONS_AT + R.PERSON_SIZE * n, R.PERSONS_AT + R.PERSON_SIZE * n + 4))
    for k in range(R.PROVINCE_COUNT):
        offs |= set(range(R.PROVINCES_AT + R.PROVINCE_SIZE * k, R.PROVINCES_AT + R.PROVINCE_SIZE * k + 4))
    return offs


def main() -> None:
    ap = argparse.ArgumentParser(description="劇本資料的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--keep", help="保留截圖的資料夾")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    skip = pointer_offsets()
    failed = 0
    for s in range(R.SCENARIO_COUNT):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(args.keep or tmp, f"scenario{s + 1}")
            if args.keep:
                os.makedirs(args.keep, exist_ok=True)
            run(args.rom, scenario_lua(s, out))
            ram = Path(out + ".ram").read_bytes()
        blk = rom.scenario_block(s)
        got = ram[R.SCENARIO_RAM - 0xFF0000:][:R.SCENARIO_SIZE]
        checked = [i for i in range(R.SCENARIO_SIZE) if i not in skip]
        diff = [i for i in checked if blk[i] != got[i]]
        failed += bool(diff)
        print(f"scenario {s + 1} {rom.scenario_title(s)}: {len(checked) - len(diff)}/{len(checked)} bytes equal "
              f"(+{len(skip)} pointer bytes skipped); persons {len(rom.persons(s))}, houses {len(rom.houses(s))}"
              + ("" if not diff else f"  NG at {[hex(i) for i in diff[:8]]}"))
    print("ALL OK" if not failed else f"{failed} scenario(s) differ")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
