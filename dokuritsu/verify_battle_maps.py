#!/usr/bin/env python3
"""Verify the battle (HEX) map layers with the game's own decoder: no battle is played; instead, on "Select side."
the first call of the LZ decoder $3C50 (Washington's face) gets its arguments replaced by those of $A69E / $A6FE
(source = BATTLE_LAYERS entry k, destination $FF7FB0), and RAM $FF7FB0 is dumped when it returns. The dumps must
equal rom.battle_layer(k); the 53 maps decoded from them are compared with the SFC version's
(~/works/superfamicom-re/dokuritsu) when that is present.

Usage: .venv/bin/python dokuritsu/verify_battle_maps.py
"""
import importlib.util
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

LZ, BUFFER = 0x3C50, 0xFF7FB0
SFC = os.path.expanduser("~/works/superfamicom-re/dokuritsu")


def decode_in_game(rom: L.Rom, k: int, size: int) -> bytes:
    events, end = schedule((BOOT + " c:20 w300").split())
    rows = ",".join(f'{{{fr},"{b}","{v}"}}' for fr, b, v in events)
    src = rom.u32(L.BATTLE_LAYERS + 4 * k)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "layer")
        lua = f"""
local ev={{{rows}}}
local armed, ret = false, nil
on_exec(0x{LZ:X}, function()
  if not armed or ret then return end
  local sp=REG("SP")
  SP:write_u32(sp+4, 0x{BUFFER:X}); SP:write_u32(sp+8, 0x{src:X})
  ret=rd32(sp)
  on_exec(ret, function()
    local t={{}}
    for i=0,{size - 1} do t[#t+1]=string.char(rd8(0x{BUFFER:X}+i)) end
    local fh=io.open("{out}", "wb"); fh:write(table.concat(t)); fh:close()
    quit()
  end)
end)
on_frame(function(f)
  for _,e in ipairs(ev) do if e[1]==f then press(e[3], e[2]=="press") end end
  if f=={end - 330} then armed=true end
  if f=={end} then quit() end
end)
"""
        run(rom.path, lua, debug=True)
        if not os.path.exists(out):
            return b""
        with open(out, "rb") as fh:
            return fh.read()


def sfc_maps() -> list[list[dict]] | None:
    if not os.path.exists(os.path.join(SFC, "rom.py")):
        return None
    sys.path.insert(0, os.path.join(os.path.dirname(SFC), "tools"))
    sys.path.insert(0, SFC)
    spec = importlib.util.spec_from_file_location("sfc_rom", os.path.join(SFC, "rom.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    s = mod.Rom()
    return [s.battle_map(m)["cells"] for m in range(L.LOCATION_COUNT)]


def main() -> None:
    rom = L.Rom()
    ok = True
    for k, name in enumerate("AB"):
        want = rom.battle_layer(k)
        got = decode_in_game(rom, k, len(want))
        same = sum(a == b for a, b in zip(got, want))
        ok &= got == want
        print(f"layer {name}: $3C50 output {same}/{len(want)} bytes equal")
    sfc = sfc_maps()
    if sfc:
        keys = ("terrain", "flags", "byte1", "overlay")
        cells = [(c, d) for m in range(L.LOCATION_COUNT) for c, d in zip(rom.battle_map(m), sfc[m])]
        same = sum(all(c[k] == d[k] for k in keys) for c, d in cells)
        print(f"SFC battle maps: {same}/{len(cells)} hexes equal (terrain, flags, byte 1, overlay)")
    print("ALL OK" if ok else "DIFFERENT")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
