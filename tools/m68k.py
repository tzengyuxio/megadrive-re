#!/usr/bin/env python3
"""Disassemble 68000 code of an MD ROM with MAME's debugger (`dasm`); capstone 5 prints some absolute short
addresses wrong ($E500 as $aaaa), MAME's disassembler doesn't.

Usage: .venv/bin/python tools/m68k.py ROM START-END [START-END ...]   # hex addresses
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mame import run


def disasm(rom_path: str, ranges: list[tuple[int, int]]) -> list[str]:
    """Lines 'ADDR: OPCODES  mnemonic operands' of each range, in order."""
    with tempfile.TemporaryDirectory() as tmp:
        cmds = "\n".join(f'  M.debugger:command("dasm {tmp}/{i}.txt,${a:x},${b - a:x},1")'
                         for i, (a, b) in enumerate(ranges))
        run(rom_path, f"on_frame(function(f) if f==2 then\n{cmds}\n  quit() end end)\n", debug=True)
        out = []
        for i in range(len(ranges)):
            with open(f"{tmp}/{i}.txt") as fh:
                out += fh.read().splitlines()
        return out


if __name__ == "__main__":
    spans = [tuple(int(x, 16) for x in s.split("-")) for s in sys.argv[2:]]
    print("\n".join(disasm(sys.argv[1], spans)))
