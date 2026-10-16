#!/usr/bin/env python3
"""Check rom.py's faces against the game's own face code, in MAME.

1. Decoder: the hero select draws the chosen hero with $B3D0 (portrait = word argument at A6+$12, LZ-decoded by
   $3C5E into the buffer at A6-$4B0, palette FACE_PALETTE loaded into CRAM line 3). A hook right after the
   decompression ($B408) reads the 960-byte buffer, puts the next portrait number in the argument and jumps back to
   $B3EC; for composite codes it calls the game's composite builder $5874(buffer, code, pack) and returns to the
   hook. So the game itself builds all 134 portraits, every composite face of the person table and, per pack, the
   code that takes part n for every part (n = 0-7), which are compared byte for byte with Rom.face_tiles.
2. Screen: the same screen with the portrait read at $B3EC patched to `move.l #n,d0`, or replaced by a call of
   $5874 for a composite code. VRAM tile 0x5A0 (30 tiles), CRAM line 3 and the 40 x 48 sprite on the screenshot
   (colour 0 is transparent) are compared with rom.py.

Usage: .venv/bin/python daikoukai2/verify_faces.py [--rom ROM] [--keep DIR]
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
from replay import replay

TO_TITLE = "w1500 start w300 start w300"      # title menu (NEW GAME); the next START opens the hero select
TO_HEROES = TO_TITLE + " start w300"
HOOK, LOOP, BUILD = 0xB408, 0xB3EC, 0x5874
FRAME = 0x4B0 + 28 + 12                         # A6 - SP at $B3EC (locals, movem, the palette call's arguments)
FACE_TILE, FACE_LINE = 0x5A0, 3
SCREEN_FACES = (77, 0x8070, 0xE5BE)             # besides the hero's own portrait 0


def all_codes(rom: R.Rom) -> tuple[list[int], list[int]]:
    persons = sorted({p["face"] for p in rom.persons() if p["face"] & 0x8000})
    cover = [0x8000 | t << 12 | n << 9 | n << 6 | n << 3 | n for t in range(R.COMPOSITE_PACKS) for n in range(8)]
    return list(range(R.PORTRAIT_COUNT)), persons + [c for c in cover if c not in persons]


def run_decoder(rom_path: str, codes: list[int], out: str) -> None:
    events, end = schedule((TO_HEROES + " w3000").split())   # each LZ decoding takes ~4 frames
    rows = ",".join(f'{{{f},"{k}","{v}"}}' for f, k, v in events)
    lua = f"""
local ev={{{rows}}}
on_frame(function(f) for _,e in ipairs(ev) do if e[1]==f then press(e[3], e[2]=="press") end end
  if f=={end} then print("NOHIT"); quit() end end)
local codes={{{",".join(str(c) for c in codes)}}}
local i=0
local fh=io.open("{out}", "w")
on_exec({HOOK:#x}, function()
  local a6=REG("A6")
  if i>0 then
    local t={{string.format("%04X ", codes[i])}}
    for a=a6-0x4B0,a6-0x4B0+{R.FACE_BYTES - 1} do t[#t+1]=string.format("%02X", rd8(a)) end
    fh:write(table.concat(t), "\\n")
  end
  i=i+1
  if i>#codes then fh:close(); print("DONE"); quit(); return end
  local c=codes[i]
  if c<0x8000 then
    SP:write_u32(a6+0x10, c); SETREG("SP", a6-{FRAME}); SETREG("PC", {LOOP:#x})
  else
    local sp=a6-{FRAME}-8-16   -- as at the hook; then return address, buffer, code, pack
    SP:write_u32(sp, {HOOK:#x}); SP:write_u32(sp+4, a6-0x4B0); SP:write_u32(sp+8, c)
    SP:write_u32(sp+12, (c >> 12) & 7)
    SETREG("SP", sp); SETREG("PC", {BUILD:#x})
  end
end)
"""
    text = run(rom_path, lua, debug=True)
    if "DONE" not in text.split():
        raise RuntimeError("face routine not reached\n" + text[-2000:])


def screen_patch(code: int) -> bytes:
    """28 bytes for $B3EC-$B407: the portrait number, or the composite builder instead of the LZ decoder."""
    if not code & 0x8000:
        return bytes.fromhex(f"203C{code:08X}")
    t = code >> 12 & 7
    # pea t.w; pea code.w; pea (-$4b0,a6); jsr $5874; addq.l #4,a7 (the stack the code after expects); nop x4
    return bytes.fromhex(f"4878{t:04X}4878{code:04X}486EFB504EB900005874588F4E714E714E714E71")


def find_face(im: Image.Image, idx: list[int], pal: list[int]) -> tuple[tuple[int, int] | None, int]:
    """(top-left corner, pixels compared) of the 40 x 48 block whose non-0 pixels equal the face's colours."""
    px = im.load()
    want = [(i % 40, i // 40, R.md_rgb(pal[v])) for i, v in enumerate(idx) if v]
    for y in range(im.height - 48 + 1):
        for x in range(im.width - 40 + 1):
            if all(px[x + dx, y + dy] == c for dx, dy, c in want):
                return (x, y), len(want)
    return None, len(want)


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像：遊戲自己的解碼結果與畫面，對 rom.py 逐 byte／逐 pixel 比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--keep", help="把模擬器輸出留在這個資料夾")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    portraits, composite = all_codes(rom)
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        folder = args.keep or tmp
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "faces.txt")
        run_decoder(args.rom, portraits + composite, path)
        got = {}
        with open(path) as fh:
            for line in fh:
                code, data = line.split()
                got[int(code, 16)] = bytes.fromhex(data)
        n_p = sum(got.get(c) == rom.face_tiles(c) for c in portraits)
        n_c = sum(got.get(c) == rom.face_tiles(c) for c in composite)
        print(f"解碼：一般頭像 {n_p}/{len(portraits)}，合成頭像 {n_c}/{len(composite)}（人物用的 "
              f"{sum(1 for c in composite if c in {p['face'] for p in rom.persons()})} 個＋各 pack 各部件）")
        ok &= n_p == len(portraits) and n_c == len(composite)

    pal = rom.face_palette()
    faces = (0,) + SCREEN_FACES
    runs = [{"rom": [] if c == 0 else [(LOOP, screen_patch(c))], "steps": "start w300", "at": 330, "shot": True,
             "read": [("vram", 32 * FACE_TILE, R.FACE_BYTES), ("cram", 32 * FACE_LINE, 32)]} for c in faces]
    for c, res in zip(faces, replay(args.rom, TO_TITLE, runs)):
        vram, cram = res["read"]
        line = [R.be16(cram, 2 * i) for i in range(16)]
        pos, n = find_face(Image.open(res["shot"]).convert("RGB"), rom.face_pixels(c), pal)
        good = vram == rom.face_tiles(c) and line == pal and pos is not None
        print(f"畫面 face {c:#06x}：VRAM tiles {'OK' if vram == rom.face_tiles(c) else 'NG'}，CRAM line 3 "
              f"{sum(a == b for a, b in zip(line, pal))}/16，截圖非透明 {n} pixel "
              + (f"全同（位置 {pos}）" if pos else "找不到相同區塊"))
        ok &= good
    print("OK" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
