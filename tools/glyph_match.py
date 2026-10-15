#!/usr/bin/env python3
"""Guess which character each 16x16 1bpp ROM glyph is, by comparing it with every JIS X 0208 character
rendered in Hiragino; prints the best candidates. The guesses are a starting point for a hand-checked
charset (use a core sheet to check them).

Usage: .venv/bin/python tools/glyph_match.py ROM FONT_OFFSET COUNT [--top 3] [--first N]
"""
import argparse
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from triage import load_rom

FONTS = ["/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc"]


def jis_chars() -> list[str]:
    out = []
    for hi in list(range(0x81, 0xA0)) + list(range(0xE0, 0xEB)):
        for lo in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
            try:
                c = bytes([hi, lo]).decode("cp932")
            except UnicodeDecodeError:
                continue
            if c.strip():
                out.append(c)
    return out


def feature(img: np.ndarray) -> np.ndarray:
    """Blurred, normalised 16x16 bitmap (shift tolerant)."""
    im = Image.fromarray((img * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
    a = np.asarray(im, dtype=np.float32).ravel()
    a -= a.mean()
    n = np.linalg.norm(a)
    return a / n if n else a


def render(chars: list[str], font: str, size: int = 16) -> np.ndarray:
    f = ImageFont.truetype(font, size)
    feats = []
    for c in chars:
        im = Image.new("L", (16, 16), 0)
        ImageDraw.Draw(im).text((8, 8), c, font=f, fill=255, anchor="mm")
        feats.append(feature(np.asarray(im) > 96))
    return np.stack(feats)


def rom_glyph(rom: bytes, off: int) -> np.ndarray:
    a = np.zeros((16, 16), bool)
    for y in range(16):
        w = rom[off + y * 2] << 8 | rom[off + y * 2 + 1]
        for x in range(16):
            a[y, x] = w >> (15 - x) & 1
    return a


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("offset")
    ap.add_argument("count", type=int)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--top", type=int, default=3)
    args = ap.parse_args()
    rom = load_rom(args.rom)
    chars = jis_chars()
    tabs = [render(chars, f) for f in FONTS]
    base = int(args.offset, 16)
    for g in range(args.first, args.count):
        v = feature(rom_glyph(rom, base + g * 32))
        score = np.maximum(*(t @ v for t in tabs))
        best = np.argsort(-score)[:args.top]
        print(g, " ".join(f"{chars[i]}{score[i]:.2f}" for i in best))


if __name__ == "__main__":
    main()
