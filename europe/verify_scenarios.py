#!/usr/bin/env python3
"""Verify the scenario, terrain and map-cell decoding against the game: for each scenario 1-6, MAME picks it on
the menu (1 player, Allies) and plays on to the battle screen, with exec hooks on the game's own loaders:
- $9E06 (after $9DC4 copies the block with memmove $7E8C): $FF0000+0x2495 must equal rom.block, and the
  scenario number in D2 must be the one picked;
- $9E4C (after $9DC4 decodes the terrain with LZ $3360 and copies it): $FF259E+1600 must equal rom.terrain_raw;
- $9EF4 (end of $9E56, battle screen): the 1600 words at $FF6D30 must equal rom.map_words(map).

Usage: .venv/bin/python europe/verify_scenarios.py [--rom ROM] [--only N]
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

TITLE = "w1800 start:10 w300 start:10 w300 c:10 w300 "         # power-on → NEW GAME → scenario list
DOWN = "down:10 w60 "                                          # list cursor starts on キャンペーンモード
# description → これで良いですか (block copy) → 何人参戦 (1人) → 連合 → 戦闘を見るか → ゲーム開始 → battle screen
TO_BATTLE = "c:10 w300 c:10 w300 c:10 w300 down:10 w60 c:10 w300 c:10 w300 c:10 w300 w600"
HOOKS = {"block": (0x9E06, R.BLOCK_RAM, R.BLOCK_SIZE), "terrain": (0x9E4C, R.TERRAIN_RAM, R.MAP_SIZE ** 2),
         "words": (0x9EF4, R.CELLS_RAM, 2 * R.MAP_SIZE ** 2)}


def scenario_lua(sc: int, out: str) -> str:
    events, end = schedule((TITLE + DOWN * sc + TO_BATTLE).split())
    rows = ",".join(f'{{{fr},"{k}","{v}"}}' for fr, k, v in events)
    hooks = "\n".join(f'on_exec(0x{pc:X}, function() save_ram("{out}_{name}", 0x{a:X}, {n}) end)'
                      for name, (pc, a, n) in HOOKS.items())
    return f"""
local ev={{{rows}}}
local function save_ram(path, a, n)
  local t={{}}
  for i=0,n-1 do t[#t+1]=string.char(rd8(a+i)) end
  local fh=io.open(path, "wb"); fh:write(table.concat(t)); fh:close()
end
on_exec(0x9DD0, function() local fh=io.open("{out}_d2", "w"); fh:write(REG("D2") & 255); fh:close() end)
{hooks}
on_frame(function(f)
  for _,e in ipairs(ev) do if e[1]==f then press(e[3], e[2]=="press") end end
  if f=={end} then quit() end
end)
"""


def read(path: str) -> bytes | None:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return fh.read()


def main() -> None:
    ap = argparse.ArgumentParser(description="劇本、地形、地圖格的模擬器驗證")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--only", type=int, help="只驗證劇本 N（1-6）")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    failed = 0
    for sc in [args.only] if args.only else range(1, R.SCENARIO_COUNT + 1):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "s")
            run(args.rom, scenario_lua(sc, out), debug=True)
            got = {name: read(f"{out}_{name}") for name in HOOKS}
            d2 = read(f"{out}_d2")
        m = rom.map_number(sc)
        want = {"block": rom.block(sc), "terrain": rom.terrain_raw(sc),
                "words": b"".join(w.to_bytes(2, "big") for w in rom.map_words(m))}
        res = []
        for name in HOOKS:
            g, w = got[name], want[name]
            if g is None:
                res.append(f"{name} not reached")
            else:
                same = sum(a == b for a, b in zip(g, w))
                res.append(f"{name} {same}/{len(w)}")
        ok = all(got[k] == want[k] for k in HOOKS) and d2 == str(sc).encode()
        failed += not ok
        title = rom.scenarios()[sc - 1]["title"]
        print(f"scenario {sc} {title} (D2={d2.decode() if d2 else '?'}, map {m}): {', '.join(res)} bytes equal"
              + ("" if ok else "  NG"))
    print("ALL OK" if not failed else f"{failed} scenario(s) differ")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
