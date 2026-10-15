"""KOEI LZ as written in C in MD 三國志III ($3374, bit reader $32FA, mask table 0x6312C).

Same stream format as the SFC games (tools/koei_lz.py): a 16-bit window W filled from little-endian words,
flag bytes and literal bytes read from the same pointer in between, flags MSB first (1 = literal). A copy
has a prefix-coded length (count = length + 1; the length code 0000000 + 1111111 ends the stream) and a
prefix-coded distance (copy from distance + 1 back). The decoder has no lookup tables, so the SFC table
block isn't in the ROM.
"""


def decompress(rom: bytes, p: int, limit: int = 1 << 20) -> tuple[bytes, int]:
    """(output, end offset) of the stream at file offset p."""
    w = n = avail = 0

    def take(bits: int) -> None:
        nonlocal w, n, avail, p
        w = (w << bits) & 0xFFFF
        if bits > avail:
            bits -= avail
            w |= ((n & ((1 << avail) - 1)) << bits) & 0xFFFF
            n = rom[p] | rom[p + 1] << 8
            p += 2
            avail = 16 - bits
        else:
            avail -= bits
        w |= (n >> avail) & ((1 << bits) - 1)

    take(16)
    out = bytearray()
    while len(out) < limit:
        flags = rom[p]
        p += 1
        for _ in range(8):
            if flags & 0x80:
                out.append(rom[p])
                p += 1
            else:
                if w & 0x8000:
                    length = 1
                else:
                    for bit, mask, shift, add, bits in ((0x4000, 0x6000, 13, 0, 2), (0x2000, 0x3800, 11, 0, 4),
                                                        (0x1000, 0x1E00, 9, 0, 6), (0x0800, 0x0F80, 7, 0, 8),
                                                        (0x0400, 0x07E0, 5, 0, 10), (0x0200, 0x03F8, 3, 0, 12)):
                        if w & bit:
                            length = (w & mask) >> shift
                            break
                    else:
                        length = ((w & 0x1FC) >> 2) + 0x80
                        if length == 0xFF:
                            return bytes(out), p
                        bits = 13
                    take(bits)
                w &= 0x7FFF
                if w < 0x800:
                    dist, bits = (w & 0x600) >> 9, 7
                elif w < 0xC00:
                    dist, bits = ((w & 0x300) >> 8) + 4, 8
                elif w < 0x1800:
                    dist, bits = (((w - 0xC00) & 0xF80) >> 7) + 8, 9
                elif w < 0x3000:
                    dist, bits = (((w - 0x1800) & 0x1FC0) >> 6) + 0x20, 10
                else:
                    k = min(w >> 12, 7)  # 3..7
                    dist, bits = ((w & 0x1FFF) | 0x1000) >> (8 - k), 8 + k
                take(bits)
                start = len(out) - dist - 1
                if start < 0:
                    raise ValueError(f"copy before the start of the output at stream offset {p:#x}")
                for i in range(length + 1):
                    out.append(out[start + i])
            flags = (flags << 1) & 0xFF
    return bytes(out), p
