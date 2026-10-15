"""Savestate replay in MAME (tools/mame.py): play a button script once, save a state, then for every run load it,
patch ROM / RAM, press more buttons, and take a screenshot and/or read memory at a given frame.

    runs = [{"rom": [(offset, bytes)], "ram": [(addr, bytes)], "steps": "c:10 w120", "at": 120,
             "shot": True, "read": [("ram", 0xFFB000, 512), ("vram", 0xC000, 128), ("cram", 0, 128)]}]
    results = replay(rom_path, "w900 start:10 ...", runs)   # [{"shot": PNG path or None, "read": [bytes]}]

"steps" use tools/drive.py syntax and count from the savestate (taken right after the boot steps); "at" is the
frame (after the savestate) of the screenshot and reads. ROM patches are undone before the next run. The
screenshots stay in a temp folder that is deleted when the Python process exits.
RAM addresses are 68000 bus addresses ($FF0000-$FFFFFF); vram/cram offsets are bytes.
"""
import atexit
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drive import schedule
from mame import run

LUA = r"""
local boot={%(boot)s}
local runs={%(runs)s}
local DIR="%(dir)s"
local BOOT_END=%(boot_end)d
local idx, t, phase = 0, 0, "boot"
local undo={}
local function hexs(s) return (s:gsub("..", function(h) return string.char(tonumber(h, 16)) end)) end
local function rdblock(kind, a, n)
  local t={}
  if kind=="ram" then for i=0,n-1 do t[#t+1]=string.char(rd8(a+i)) end
  elseif kind=="vram" then for i=0,n-1 do t[#t+1]=string.char(vram(a+i)) end
  elseif kind=="cram" then for i=0,n-1,2 do local w=cram((a+i)>>1); t[#t+1]=string.char(w >> 8, w & 255) end
  elseif kind=="rom" then for i=0,n-1 do t[#t+1]=string.char(rom_read(a+i)) end end
  return table.concat(t)
end
local function apply(list, f)
  for _,e in ipairs(list) do if e[1]==f then press(e[3], e[2]=="press") end end
end
on_frame(function(f)
  if phase=="boot" then
    apply(boot, f)
    if f==BOOT_END then save("replay"); phase="next" end
    return
  end
  if phase=="next" then
    for _,u in ipairs(undo) do rom_write(u[1], u[2]) end
    undo={}
    idx=idx+1
    if idx>#runs then print("DONE"); quit(); return end
    load("replay"); phase="patch"; return
  end
  if phase=="patch" then  -- first frame after the load
    local r=runs[idx]
    for _,p in ipairs(r.rom) do
      local s=hexs(p[2]); undo[#undo+1]={p[1], rdblock("rom", p[1], #s)}; rom_write(p[1], s)
    end
    for _,p in ipairs(r.ram) do local s=hexs(p[2]); for k=1,#s do wr8(p[1]+k-1, s:byte(k)) end end
    for _,b in ipairs({"a","b","c","start","up","down","left","right"}) do press(b, false) end
    t=0; phase="run"
  end
  if phase=="run" then
    local r=runs[idx]
    t=t+1
    apply(r.steps, t)
    if t==r.at then
      if r.shot then shot(DIR.."/"..idx..".png") end
      for k,q in ipairs(r.read) do
        local fh=io.open(DIR.."/"..idx.."_"..k..".bin", "wb"); fh:write(rdblock(q[1], q[2], q[3])); fh:close()
      end
      phase="next"
    end
  end
end)
"""


def _events(steps: str) -> str:
    events, _ = schedule(steps.split()) if steps else ([], 0)
    # drive.schedule starts at frame 10; replay steps start at frame 1
    return ",".join(f'{{{fr - 9},"{k}","{v}"}}' for fr, k, v in events if k != "shot")


def replay(rom_path: str, boot: str, runs: list[dict], timeout: float = 7200) -> list[dict]:
    events, boot_end = schedule(boot.split())
    boot_lua = ",".join(f'{{{fr},"{k}","{v}"}}' for fr, k, v in events if k != "shot")
    out_dir = tempfile.mkdtemp(prefix="replay_")
    atexit.register(shutil.rmtree, out_dir, True)
    rows = []
    for r in runs:
        rom = ",".join(f'{{{a},"{b.hex()}"}}' for a, b in r.get("rom", []))
        ram = ",".join(f'{{{a},"{b.hex()}"}}' for a, b in r.get("ram", []))
        reads = ",".join(f'{{"{k}",{a},{n}}}' for k, a, n in r.get("read", []))
        rows.append(f'{{rom={{{rom}}},ram={{{ram}}},steps={{{_events(r.get("steps", ""))}}},at={r["at"]},'
                    f'shot={"true" if r.get("shot") else "false"},read={{{reads}}}}}')
    lua = LUA % {"boot": boot_lua, "runs": ",".join(rows), "dir": out_dir, "boot_end": boot_end}
    text = run(rom_path, lua, timeout=timeout)
    if "DONE" not in text:
        raise RuntimeError("replay did not finish")
    results = []
    for i, r in enumerate(runs, 1):
        reads = []
        for k in range(1, len(r.get("read", [])) + 1):
            with open(f"{out_dir}/{i}_{k}.bin", "rb") as fh:
                reads.append(fh.read())
        shot = f"{out_dir}/{i}.png" if r.get("shot") else None
        results.append({"shot": shot, "read": reads})
    return results
