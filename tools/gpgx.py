#!/usr/bin/env python3
"""Run Mega-CD images in Genesis Plus GX (libretro core, driven from Python with ctypes): frame stepping, pad
input, screenshots, main / sub 68000 memory and registers, PC breakpoints. MAME's megacdj does not boot the KOEI
discs (docs/PLAYBOOK.md), Genesis Plus GX does.

    with Emu("roms/megacd/... (Japan).7z") as emu:
        emu.run(900); emu.tap("start"); emu.run(3000)
        emu.shot("title.png"); emu.prg_ram()[0x2000:0x2010]

The core is built once into .emu/ (gitignored) from a pinned Genesis Plus GX commit with tools/gpgx/probe.c
included and the PATCHES below (breakpoint checks in both CPUs' run loops):

    .venv/bin/python tools/gpgx.py --build

The BIOS is the Japanese Mega-CD 2 v2.00 (CRC dd6cc972, roms/megacd/bios/), copied to .emu/system/bios_CD_J.bin: with
the Model 1 BIOSes (v1.00G/P, v1.11) the KOEI discs are read but not booted (the BIOS starts its CD player).
Memory views are big-endian bytes as the 68000 sees them (the core keeps 16-bit words in host order).
"""
import argparse
import ctypes as C
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import megacd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMU = os.path.join(REPO, ".emu")
SRC = os.path.join(EMU, "gpgx")
CORE = os.path.join(SRC, "genesis_plus_gx_libretro.dylib")
SYSTEM = os.path.join(EMU, "system")
COMMIT = "aa74d79"
URL = "https://github.com/libretro/Genesis-Plus-GX.git"
BIOS = os.path.join(REPO, "roms", "megacd", "bios", "Mega-CD 2 (J) v2.00.bin")
PROBE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpgx", "probe.c")
PATCHES = [  # (file, anchor, text inserted before the anchor)
    ("core/m68k/m68kcpu.c", "    /* Decode next instruction */\n    REG_IR = m68ki_read_imm_16();\n\n    /* 68K bus",
     "    if (gpgx_bp_n[0]) gpgx_check_bp(0, REG_PC);\n"),
    ("core/m68k/s68kcpu.c", "    /* Decode next instruction */\n    REG_IR = m68ki_read_imm_16();",
     "    if (gpgx_bp_n[1]) gpgx_check_bp(1, REG_PC);\n"),
    ("core/m68k/m68k.h", "/* Registers used by m68k_get_reg() and m68k_set_reg() */",
     "extern int gpgx_bp_n[2];\nextern void gpgx_check_bp(int cpu, unsigned int pc);\n\n"),
]
REGS = {f"D{i}": i for i in range(8)} | {f"A{i}": 8 + i for i in range(8)} | {"PC": 16, "SR": 17, "SP": 18}
PAD = {"b": 0, "start": 3, "up": 4, "down": 5, "left": 6, "right": 7, "c": 8, "a": 1}  # RetroPad ids (Y = A)


def build() -> None:
    if not os.path.isdir(SRC):
        subprocess.run(["git", "clone", URL, SRC], check=True)
    subprocess.run(["git", "-C", SRC, "checkout", "-q", COMMIT], check=True)
    for name, anchor, text in PATCHES:
        path = Path(SRC, name)
        s = path.read_text(encoding="latin-1")
        if text not in s:
            assert s.count(anchor) == 1, f"anchor not unique in {name}"
            path.write_text(s.replace(anchor, text + anchor), encoding="latin-1")
    lib = Path(SRC, "libretro", "libretro.c")
    s = lib.read_text(encoding="latin-1")
    inc = f'\n#include "{PROBE}"\n'
    if inc not in s:
        lib.write_text(s + inc, encoding="latin-1")
    subprocess.run(["make", "-f", "Makefile.libretro", "-j8"], cwd=SRC, check=True)
    os.makedirs(SYSTEM, exist_ok=True)
    shutil.copy(BIOS, os.path.join(SYSTEM, "bios_CD_J.bin"))


# core options: a 1 Mbit backup RAM cartridge (the KOEI games need more blocks than the internal BRAM has)
OPTIONS = {"genesis_plus_gx_cart_size": "1meg", "genesis_plus_gx_system_bram": "per game",
           "genesis_plus_gx_cart_bram": "per game"}


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
SAMPLE = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
BATCH = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL = C.CFUNCTYPE(None)
STATE = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
BP = C.CFUNCTYPE(None, C.c_int, C.c_uint)


def swab(b: bytes) -> bytes:
    a = bytearray(b)
    a[0::2], a[1::2] = b[1::2], b[0::2]
    return bytes(a)


class Emu:
    """One core per process (the core keeps its state in globals)."""

    def __init__(self, image: str):
        if not os.path.exists(CORE):
            build()
        self.lib = C.CDLL(CORE)
        self.frame, self.held, self.pixels, self.size = 0, set(), b"", (0, 0)
        self._bp = {}
        self._sysdir = C.create_string_buffer(SYSTEM.encode())  # buffers the core keeps pointers to
        self._tmp = tempfile.TemporaryDirectory()  # saves (BRAM) start empty on every run
        self._savedir = C.create_string_buffer(self._tmp.name.encode())
        self._values = {k.encode(): C.create_string_buffer(v.encode()) for k, v in OPTIONS.items()}
        self._cbs = [ENV(self._env), VIDEO(self._video), SAMPLE(lambda left, right: None),
                     BATCH(lambda data, n: n), POLL(lambda: None), STATE(self._input), BP(self._hit)]
        lib = self.lib
        lib.retro_set_environment(self._cbs[0])
        lib.retro_set_video_refresh(self._cbs[1])
        lib.retro_set_audio_sample(self._cbs[2])
        lib.retro_set_audio_sample_batch(self._cbs[3])
        lib.retro_set_input_poll(self._cbs[4])
        lib.retro_set_input_state(self._cbs[5])
        lib.retro_init()
        self._cue = megacd.cue(image).encode()
        lib.retro_load_game.restype = C.c_bool
        assert lib.retro_load_game(C.byref(GameInfo(self._cue, None, 0, None))), "retro_load_game failed"
        C.c_void_p.in_dll(lib, "gpgx_bp_cb").value = C.cast(self._cbs[6], C.c_void_p).value
        for f in ("gpgx_prg_ram", "gpgx_word_ram_2m", "gpgx_work_ram", "gpgx_vram", "gpgx_cram", "gpgx_vsram",
                  "gpgx_vdp_reg", "gpgx_word_ram"):
            getattr(lib, f).restype = C.c_void_p
        lib.gpgx_reg.restype = C.c_uint

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.lib.retro_unload_game()
        self.lib.retro_deinit()
        self._tmp.cleanup()

    # --- libretro callbacks ---

    def _env(self, cmd: int, data: int) -> bool:
        cmd &= 0xFFFF
        if cmd in (9, 31):            # GET_SYSTEM_DIRECTORY, GET_SAVE_DIRECTORY
            C.cast(data, C.POINTER(C.c_void_p))[0] = C.addressof(self._sysdir if cmd == 9 else self._savedir)
            return True
        if cmd == 15:                 # GET_VARIABLE
            key = C.cast(data, C.POINTER(C.c_char_p))[0]
            if key in self._values:
                C.cast(data, C.POINTER(C.c_void_p))[1] = C.addressof(self._values[key])
                return True
            return False
        if cmd == 10:                 # SET_PIXEL_FORMAT
            self.fmt = C.cast(data, C.POINTER(C.c_int))[0]
            return True
        if cmd == 3:                  # GET_CAN_DUPE
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        return False

    def _video(self, data: int, w: int, h: int, pitch: int) -> None:
        if data:
            self.pixels, self.size, self.pitch = C.string_at(data, pitch * h), (w, h), pitch

    def _input(self, port: int, device: int, index: int, ident: int) -> int:
        if port or device != 1:
            return 0
        if ident == 256:              # RETRO_DEVICE_ID_JOYPAD_MASK, which the core asks for
            return sum(1 << b for b in self.held)
        return int(ident in self.held)

    def _hit(self, cpu: int, pc: int) -> None:
        for fn in self._bp.get((cpu, pc), []):
            fn(self)

    # --- control ---

    def run(self, frames: int = 1, until=None) -> None:
        """Step frames; stop early when until(emu) is true."""
        for _ in range(frames):
            self.lib.retro_run()
            self.frame += 1
            if until and until(self):
                return

    def save(self) -> bytes:
        self.lib.retro_serialize_size.restype = C.c_size_t
        buf = C.create_string_buffer(self.lib.retro_serialize_size())
        assert self.lib.retro_serialize(buf, C.c_size_t(len(buf)))
        return buf.raw

    def load(self, state: bytes) -> None:
        assert self.lib.retro_unserialize(C.c_char_p(state), C.c_size_t(len(state)))

    def press(self, *buttons: str) -> None:
        self.held = {PAD[b] for b in buttons}

    def tap(self, button: str, hold: int = 30, after: int = 30) -> None:
        """The KOEI CD games poll the pad slowly: hold buttons for about 30 frames."""
        self.press(button)
        self.run(hold)
        self.press()
        self.run(after)

    def breakpoint(self, cpu: int, pc: int, fn) -> None:
        """fn(emu) when the CPU (0 main, 1 sub) is about to execute pc; registers via reg()/set_reg()."""
        self._bp.setdefault((cpu, pc), []).append(fn)
        pcs = sorted({p for c, p in self._bp if c == cpu})
        (C.c_uint * 32 * 2).in_dll(self.lib, "gpgx_bp")[cpu][:len(pcs)] = pcs
        (C.c_int * 2).in_dll(self.lib, "gpgx_bp_n")[cpu] = len(pcs)

    def clear_breakpoints(self) -> None:
        self._bp.clear()
        (C.c_int * 2).in_dll(self.lib, "gpgx_bp_n")[:] = [0, 0]

    def reg(self, cpu: int, name: str) -> int:
        return self.lib.gpgx_reg(cpu, REGS[name])

    def set_reg(self, cpu: int, name: str, value: int) -> None:
        self.lib.gpgx_set_reg(cpu, REGS[name], C.c_uint(value))

    # --- memory (big-endian views) ---

    def _mem(self, fn: str, size: int, *args) -> bytes:
        return swab(C.string_at(getattr(self.lib, fn)(*args), size))

    def _poke(self, fn: str, off: int, data: bytes, *args) -> None:
        base = getattr(self.lib, fn)(*args)
        for i, v in enumerate(data):
            C.c_uint8.from_address(base + ((off + i) ^ 1)).value = v

    def prg_ram(self) -> bytes:
        return self._mem("gpgx_prg_ram", 0x80000)

    def write_prg_ram(self, off: int, data: bytes) -> None:
        self._poke("gpgx_prg_ram", off, data)

    def word_ram_2m(self) -> bytes:
        return self._mem("gpgx_word_ram_2m", 0x40000)

    def work_ram(self) -> bytes:
        return self._mem("gpgx_work_ram", 0x10000)

    def vram(self) -> bytes:
        return self._mem("gpgx_vram", 0x10000)

    def cram(self) -> list[int]:
        """64 MD colour words (0000BBB0GGG0RRR0); the core stores them packed as 9-bit BBBGGGRRR."""
        raw = C.string_at(self.lib.gpgx_cram(), 0x80)
        out = []
        for i in range(64):
            v = raw[2 * i] | raw[2 * i + 1] << 8
            out.append((v & 0x1C0) << 3 | (v & 0x38) << 2 | (v & 7) << 1)
        return out

    def shot(self, path: str) -> None:
        from PIL import Image
        w, h = self.size
        im = Image.frombuffer("RGB", (w, h), self.pixels, "raw", "BGR;16", self.pitch, 1)
        im.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Genesis Plus GX（libretro）驅動 Mega-CD 映像")
    ap.add_argument("--build", action="store_true", help="下載並編譯 core 到 .emu/")
    ap.add_argument("--shot", nargs=2, metavar=("IMAGE", "PNG"), help="開機、按 Start，截第 3000 格的畫面")
    args = ap.parse_args()
    if args.build:
        build()
    if args.shot:
        with Emu(args.shot[0]) as emu:
            emu.run(1300)
            emu.tap("start")
            emu.run(3000 - emu.frame)
            emu.shot(args.shot[1])


if __name__ == "__main__":
    main()
