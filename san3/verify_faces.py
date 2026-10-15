#!/usr/bin/env python3
"""Check rom.py's faces against the game's own face code, in two MAME runs.

1. Decoder: at the first face load ($F42C) the hook at $F466 (D2 saved, return address and argument on the stack)
   reads the 960-byte buffer $FFB004 and the palette number $FF813C, puts the next face code in the argument
   and jumps back to $F42E. So the game itself builds all 307 plain faces and every composite face of the person
   table, which are compared byte for byte with Rom.face_tiles / face_palette_no.
2. Screen: play scenario 1 as 劉備 up to the command menu; the province panel shows 劉備's face (VRAM tile
   0x208, CRAM line 3). VRAM tiles, the 16 CRAM colours (15 loaded + the screen's colour 15) and the 40x48
   pixels of the screenshot are compared with rom.py. Two more runs give every face load another face
   (SCREEN_FACES: one with palette 1 and colour 15, one composite).

Usage: .venv/bin/python san3/verify_faces.py [--rom ROM] [--keep DIR]
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

TO_RULERS = "w1500 a:20 w200 start:30 w300 w20 w300 w20 w300 start:5 w300 c:10 w300 c:10 w300 up:6 w30 c:10 w300"
TO_MENU = TO_RULERS + (" right:6 w30 right:6 w30 c:10 w300 c:10 w300 c:10 w300 c:10 w300 c:10 w300"
                       " c:10 w600 w600 w600 c:10 w200")
LIU_BEI = 0xA1
FACE_TILE = 0x208
FACE_LINE = 3
# 劉備's own face; 77 (palette 1, uses colour 15); a composite face (阿会喃)
SCREEN_FACES = (LIU_BEI, 77, 0x8DA4)


def press_lua(steps: str) -> tuple[str, int]:
    events, end = schedule(steps.split())
    rows = ",".join(f'{{{f},"{k}","{v}"}}' for f, k, v in events if k != "shot")
    return f"""
local ev={{{rows}}}
on_frame(function(f) for _,e in ipairs(ev) do if e[1]==f then press(e[3], e[2]=="press") end end end)
""", end


def run_decoder(rom_path: str, faces: list[int], out: str) -> None:
    lua, end = press_lua(TO_MENU + " w600")
    codes = ",".join(str(f) for f in faces)
    lua += f"""
local faces={{{codes}}}
local i=0
local orig=nil
local fh=io.open("{out}", "w")
on_frame(function(f) if f=={end} then fh:close(); print("NOHIT"); quit() end end)
on_exec(0xF466, function()
  local sp=REG("SP")
  if i>0 then
    local t={{string.format("%04X %02X ", faces[i], rd8(0xFF813C))}}
    for a=0xFFB004,0xFFB004+{R.FACE_BYTES - 1} do t[#t+1]=string.format("%02X", rd8(a)) end
    fh:write(table.concat(t), "\\n")
  else
    orig=rd32(sp+8)
  end
  if i<#faces then
    i=i+1
    SP:write_u32(sp+8, faces[i])
    SETREG("PC", 0xF42E)
  else
    fh:close(); print("DONE"); quit()
  end
end)
"""
    text = run(rom_path, lua, debug=True)
    if "DONE" not in text.split():
        raise RuntimeError("face loader not reached\n" + text[-2000:])


def run_screen(rom_path: str, prefix: str, face: int) -> None:
    """Command menu screen; every face load ($F42C, argument at SP+4) is given `face` instead of its own."""
    lua, end = press_lua(TO_MENU)
    lua += f'on_frame(function(f) if f=={end} then shot("{prefix}.png"); dump("{prefix}"); quit() end end)\n'
    if face != LIU_BEI:
        lua += f'on_exec(0xF42C, function() SP:write_u32(REG("SP")+4, {face}) end)\n'
    run(rom_path, lua, debug=face != LIU_BEI)


def find_face(im: Image.Image, idx: list[int], pal: list[int]) -> tuple[tuple[int, int] | None, int]:
    """(top-left corner, pixels compared) of the 40x48 block whose non-0 pixels (0 is transparent) all equal
    the face's colours."""
    px = im.load()
    w = R.FACE_W * 8
    want = [(i % w, i // w, R.md_rgb(pal[v])) for i, v in enumerate(idx) if v]
    for y in range(im.height - R.FACE_H * 8 + 1):
        for x in range(im.width - w + 1):
            if all(px[x + dx, y + dy] == c for dx, dy, c in want):
                return (x, y), len(want)
    return None, len(want)


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像：遊戲自己的解碼結果與畫面，對 rom.py 逐 byte／逐 pixel 比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--keep", help="把模擬器輸出留在這個資料夾")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    composite = sorted({p["face"] for p in rom.persons() if p["face"] & 0x8000 and p["face"] != R.NONE16})
    faces = list(range(1, R.FACE_COUNT + 1)) + composite
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        folder = args.keep or tmp
        os.makedirs(folder, exist_ok=True)

        path = os.path.join(folder, "faces.txt")
        run_decoder(args.rom, faces, path)
        got = {}
        with open(path) as fh:
            for line in fh:
                code, pal, data = line.split()
                got[int(code, 16)] = (int(pal, 16), bytes.fromhex(data))
        n_plain = sum(got.get(f) == (rom.face_palette_no(f), rom.face_tiles(f)) for f in faces[:R.FACE_COUNT])
        n_comp = sum(got.get(f) == (rom.face_palette_no(f), rom.face_tiles(f)) for f in composite)
        print(f"解碼：一般頭像 {n_plain}/{R.FACE_COUNT}，合成頭像 {n_comp}/{len(composite)}（tiles＋調色盤號）")
        ok &= n_plain == R.FACE_COUNT and n_comp == len(composite)

        for face in SCREEN_FACES:
            prefix = os.path.join(folder, f"screen_{face:04X}")
            run_screen(args.rom, prefix, face)
            with open(prefix + ".vram", "rb") as fh:
                vram = fh.read()
            with open(prefix + ".cram", "rb") as fh:
                cram = fh.read()
            tiles_ok = vram[32 * FACE_TILE:32 * FACE_TILE + R.FACE_BYTES] == rom.face_tiles(face)
            pal = rom.face_palette(face)
            line = [R.be16(cram, 32 * FACE_LINE + 2 * i) for i in range(16)]
            im = Image.open(prefix + ".png").convert("RGB")
            pos, n = find_face(im, rom.face_pixels(face), pal)
            print(f"畫面 face {face:#06x}：VRAM tiles {'OK' if tiles_ok else 'NG'}，CRAM 16 色 "
                  f"{sum(a == b for a, b in zip(line, pal))}/16，截圖非透明 {n} pixel "
                  + (f"全同（位置 {pos}）" if pos else "找不到相同區塊"))
            ok &= tiles_ok and line == pal and pos is not None
    print("OK" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
