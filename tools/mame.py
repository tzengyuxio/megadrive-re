"""Run an MD ROM headless in MAME with a Lua script; the shared Lua prelude gives frame counting, pad input,
screenshots, memory dumps, read tracing and exec hooks.

    out = run(rom_path, lua, debug=True)   # stdout of MAME (the Lua print() lines)

Prelude API (Lua):
  FRAME()                   frame number (1 = first frame done)
  on_frame(fn)              fn(frame) after every frame
  press(btn, on)            btn: a b c start up down left right (x y z mode on 6-button pads are not used)
  shot(path)                PNG of the screen
  dump(prefix)              prefix.ram (64 KB at $FF0000), .vram (64 KB), .cram (128), .vsram (80), .regs (24)
  rd8(a) rd16(a) rd32(a)    68000 bus reads; wr8(a, v) wr16 writes
  rom_write(off, bytes)     patch the cartridge ROM (what the CPU reads)
  vram(a) / cram(i)         VDP memory (byte / CRAM word i)
  on_exec(pc, fn)           fn() each time the CPU is about to execute pc (needs debug=True); REG("D0") etc.
                            (register names as MAME's state: "SP" and "PC", not "A7")
  save(name) / load(name)   savestates (take effect at the end of the frame)
  SP:install_read_tap / install_write_tap   keep the returned handle in a global, or it is garbage-collected
                            and the tap stops
  quit()
  Mega-CD (run() on a .7z/.cue image): SUB / SUBSP are the sub CPU (PRG-RAM at $000000); srd8/16/32, swr8/16

The ROM is extracted from its zip into a temp folder, which is deleted afterwards. MAME needs no BIOS for
megadrij / genesis. Mega-CD images run on megacdj with the v1.11 BIOS from roms/megacd/bios/megacdj.zip and the
bin/cue that tools/megacd.py unpacks; MAME 0.289's megacdj (preliminary) only reaches the BIOS / CD player with the
KOEI discs, so it cannot verify them.
"""
import os
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import megacd

SYSTEM = {"J": "megadrij", "U": "genesis", "E": "megadriv"}
CD_BIOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "roms", "megacd", "bios")

PRELUDE = r"""
local M=manager.machine
local CPU=M.devices[":maincpu"]
local SP=CPU.spaces["program"]
local VDP=M.devices[":gen_vdp"]
local function item(name) return emu.item(VDP.items["0/"..name]) end
local VRAM, CRAM, VSRAM, REGS = item("m_vram"), item("m_cram"), item("m_vsram"), item("m_regs")
local PAD=M.ioport.ports[":ctrl1:mdpad:PAD"]
local BTN={a="P1 A", b="P1 B", c="P1 C", start="P1 Start", up="P1 Up", down="P1 Down", left="P1 Left",
           right="P1 Right"}
local ROM=M.memory.regions[":mdslot:cart:rom"]
SUB=M.devices[":segacd:segacd_68k"]
SUBSP=SUB and SUB.spaces["program"]
function srd8(a) return SUBSP:read_u8(a) end
function srd16(a) return SUBSP:read_u16(a) end
function srd32(a) return SUBSP:read_u32(a) end
function swr8(a, v) SUBSP:write_u8(a, v) end
function swr16(a, v) SUBSP:write_u16(a, v) end
local _f=0
local _frame_fns={}
local _exec={}
function FRAME() return _f end
function on_frame(fn) _frame_fns[#_frame_fns+1]=fn end
function press(b, on) PAD.fields[BTN[b]]:set_value(on and 1 or 0) end
function shot(path) M.screens[":megadriv"]:snapshot(path) end
function rd8(a) return SP:read_u8(a) end
function rd16(a) return SP:read_u16(a) end
function rd32(a) return SP:read_u32(a) end
function wr8(a, v) SP:write_u8(a, v) end
function wr16(a, v) SP:write_u16(a, v) end
function REG(r) return CPU.state[r].value end
function SETREG(r, v) CPU.state[r].value=v end
function vram(a) local w=VRAM:read(a >> 1); return (a & 1)==0 and (w >> 8) or (w & 255) end
function cram(i) return CRAM:read(i) end
local function swab(s) return (s:gsub("(.)(.)", "%2%1")) end  -- items hold host-order (little-endian) words
function rom_write(off, s) for k=1,#s do ROM:write_u8(off+k-1, s:byte(k)) end end
function rom_read(off) return ROM:read_u8(off) end
local function wfile(path, s) local fh=io.open(path, "wb"); fh:write(s); fh:close() end
function dump(prefix)
  local t={}
  for a=0xFF0000,0xFFFFFF,2 do local w=SP:read_u16(a); t[#t+1]=string.char(w >> 8, w & 255) end
  wfile(prefix..".ram", table.concat(t)); t={}
  wfile(prefix..".vram", swab(VRAM:read_block(0, 0x10000)))
  wfile(prefix..".cram", swab(CRAM:read_block(0, 128)))
  wfile(prefix..".vsram", swab(VSRAM:read_block(0, 80)))
  for i=0,23 do t[#t+1]=string.char(REGS:read(i) & 255) end
  wfile(prefix..".regs", table.concat(t))
end
function save(name) M:save(name) end
function load(name) M:load(name) end
function quit() M:exit() end
function on_exec(pc, fn)
  if not _exec[pc] then _exec[pc]={}; CPU.debug:bpset(pc, "", "") end
  table.insert(_exec[pc], fn)
end
if M.debugger then
  local dbg=M.debugger
  emu.register_periodic(function()
    if dbg.execution_state=="stop" then
      local fns=_exec[CPU.state["CURPC"].value]
      if fns then for _,fn in ipairs(fns) do fn() end end
      dbg.execution_state="run"
    end
  end)
end
emu.register_frame_done(function()
  _f=_f+1
  for _,fn in ipairs(_frame_fns) do fn(_f) end
end)
"""


def extract(path: str, folder: str) -> str:
    """Path of a plain ROM file for MAME: the .md inside a zip is written to folder."""
    if not path.lower().endswith(".zip"):
        return os.path.abspath(path)
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith((".md", ".bin", ".gen")))
        out = os.path.join(folder, "rom.md")
        with open(out, "wb") as fh:
            fh.write(z.read(name))
    return out


def system_for(rom: bytes) -> str:
    """MAME system from the header's region field (Japanese first)."""
    region = rom[0x1F0:0x1F3].decode("ascii", "replace")
    for r in "JUE":
        if r in region:
            return SYSTEM[r]
    return "megadrij"


def run(rom_path: str, lua: str, debug: bool = False, timeout: float = 3600, system: str | None = None) -> str:
    """Run MAME on the ROM with PRELUDE + lua until the script calls quit(); return stdout."""
    with tempfile.TemporaryDirectory() as tmp:
        if megacd.is_image(rom_path):
            media = ["-cdrom", megacd.cue(rom_path), "-bios", "v111", "-rompath", CD_BIOS]
            system = system or "megacdj"
        else:
            rom = extract(rom_path, tmp)
            media = ["-cart", rom]
            if system is None:
                with open(rom, "rb") as fh:
                    system = system_for(fh.read(0x200))
        script = os.path.join(tmp, "run.lua")
        with open(script, "w") as fh:
            fh.write(PRELUDE + lua)
        cmd = ["mame", system, *media, "-video", "none", "-sound", "none", "-nothrottle", "-skip_gameinfo",
               "-nvram_directory", os.path.join(tmp, "nvram"), "-cfg_directory", os.path.join(tmp, "cfg"),
               "-state_directory", os.path.join(tmp, "sta"), "-snapshot_directory", tmp,
               "-keyboardprovider", "none", "-mouseprovider", "none", "-joystickprovider", "none",
               "-lightgunprovider", "none", "-autoboot_script", script]
        if debug:
            cmd += ["-debug", "-debugger", "none"]
        # SDL dummy drivers + no input providers: MAME stays a background process and doesn't take the focus
        env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
        p = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout, cwd=tmp, env=env)
        errors = [line for line in p.stdout.splitlines() + p.stderr.splitlines() if "LUA ERROR" in line]
        if errors:
            raise RuntimeError("\n".join(errors[:10]))
        return p.stdout
