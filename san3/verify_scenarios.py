#!/usr/bin/env python3
"""Check rom.py's scenario tables against what the game's loader puts in RAM, for all 6 scenarios.

MAME runs the game to the scenario list, picks scenario n and, when the loader $1BC64 has run all its copy
routines ($1BCB4), saves work RAM. The RAM records are then compared field by field with rom.py:
header ($FF0788), item owners (person +4 bits), persons ($FF1562 + 30 i), provinces ($FF07C4 + 52 k),
factions ($FF1148 + 50 k), the 22-entry extra table ($FF111C, one per word) and item owners ($FF07AA).

Usage: .venv/bin/python san3/verify_scenarios.py [--rom ROM] [--dump DIR | --load DIR]
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

BOOT = "w1500 a:20 w200 start:30 w300 w20 w300 w20 w300 start:5 w300 c:10 w300"
LOADED = 0x1BCB4
RAM = 0xFF0000


def capture(rom_path: str, sc: int, out: str) -> None:
    steps = BOOT + " down:6 w30" * sc + " c:10 w600"
    events, end = schedule(steps.split())
    rows = ",".join(f'{{{f},"{k}","{v}"}}' for f, k, v in events if k != "shot")
    lua = f"""
local ev={{{rows}}}
on_frame(function(f)
  for _,e in ipairs(ev) do if e[1]==f then press(e[3], e[2]=="press") end end
  if f=={end} then print("NOHIT"); quit() end
end)
on_exec({LOADED}, function()
  local t={{}}
  for a=0xFF0000,0xFFFFFF,2 do local w=rd16(a); t[#t+1]=string.char(w >> 8, w & 255) end
  local fh=io.open("{out}", "wb"); fh:write(table.concat(t)); fh:close()
  print("HIT"); quit()
end)
"""
    text = run(rom_path, lua, debug=True)
    if "HIT" not in text.split():
        raise RuntimeError(f"scenario {sc + 1}: loader not reached")


def check(rom: R.Rom, sc: int, ram: bytes) -> dict[str, tuple[int, int]]:
    def b(a: int) -> int:
        return ram[a - RAM]

    def w(a: int) -> int:
        return R.be16(ram, a - RAM)

    res = {}
    header = rom.scenario_header(sc)["raw"]
    res["header"] = (int(ram[0x0788:0x0788 + 34] == header), 1)

    provs = rom.scenario_provinces(sc)
    pf = rom.province_factions(sc)
    ok = 0
    for p in provs:
        a = 0xFF07C4 + 52 * p["id"]
        r = p["raw"]
        got = [w(a + 0xA), w(a + 0xC) * 100, w(a + 0xE), R.be32(ram, a + 0x10 - RAM), b(a + 0x14),
               b(a + 0x15), b(a + 0x16), b(a + 0x17), b(a + 0x1C), b(a + 0x1E), b(a + 0x1F), w(a + 0x20),
               b(a + 0x22), b(a + 0x23), w(a + 0x24), w(a + 0x26), w(a + 0x28), b(a + 0x2B), b(a + 0x2C),
               b(a + 0x2D)]
        want = [p["w1"], p["population"], p["gold"], p["food"], pf.get(p["id"], 0xFF),
                p["b9"], p["b10"], p["b11"], p["develop"], p["b13"], p["flood"], p["commerce"],
                p["tax"], p["loyalty"], p["w19"], p["w21"], p["w23"], p["b25"], p["b26"], p["b27"]]
        ok += got == want and r[1] == 0 and r[31] == 0
    res["provinces"] = (ok, len(provs))

    ok = 0
    facs = rom.scenario_factions(sc)
    for fa in facs:
        a = 0xFF1148 + 50 * fa["id"]
        ok += [w(a), b(a + 0xE), list(ram[a + 0xF - RAM:a + 0x24 - RAM])] == [fa["ruler"], fa["b3"], fa["rel"]]
    res["factions"] = (ok, len(facs))

    items = rom.items()
    ok = 0
    persons, statics = rom.scenario_persons(sc), rom.persons()
    for sp in persons:
        a = 0xFF1562 + 30 * sp["id"]
        st = statics[sp["id"]]
        bits = sum(1 << i for i, it in enumerate(items) if it["owners"][sc] == sp["id"])
        rank = sp["rank_byte"]
        in_faction = rank != 0xFF and rank & 0x7F <= 4
        prov = sp["province"]
        trained = rank != 0xFF and rank & 0x7F < 4 and sp["soldiers"] and prov != 0xFF
        want = [sp["soldiers"], bits, st["raw"][2], st["raw"][3], st["flags4"], 0 if rank == 0xFF else rank & 0x7F,
                st["affinity"], st["duty"], sp["loyalty"], prov]
        got = [w(a + 2), w(a + 4), b(a + 6), b(a + 7), b(a + 0xA), b(a + 0xC), b(a + 0xD), b(a + 0xE), b(a + 0xF),
               b(a + 0x10)]
        if rank == 0xFF:
            want.append(0x10)
            got.append(b(a + 8))
        if prov != 0xFF:  # the game indexes province FF out of the table for these
            want += [pf.get(prov, 0xFF) if in_faction else 0xFF,
                     provs[prov]["training"] if trained else 0, provs[prov]["morale"] if trained else 0]
            got += [b(a + 0x11), b(a + 0x15), b(a + 0x16)]
        ok += got == want
    res["persons"] = (ok, len(persons))

    extra = rom.scenario_extra(sc)
    res["extra"] = (sum(b(0xFF111C + 2 * i) == v for i, v in enumerate(extra)), len(extra))
    res["items"] = (sum(w(0xFF07AA + 2 * i) == it["owners"][sc] for i, it in enumerate(items)), len(items))
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description="6 劇本的 RAM 與 rom.py 逐欄比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--dump", help="把 RAM 存到這個資料夾")
    ap.add_argument("--load", help="不跑模擬器，讀 --dump 存的 RAM")
    args = ap.parse_args()
    rom = R.Rom(args.rom)
    all_ok = True
    with tempfile.TemporaryDirectory() as tmp:
        folder = args.load or args.dump or tmp
        os.makedirs(folder, exist_ok=True)
        for sc in range(R.SCENARIO_COUNT):
            path = os.path.join(folder, f"scenario{sc + 1}.ram")
            if not args.load:
                capture(args.rom, sc, path)
            with open(path, "rb") as fh:
                res = check(rom, sc, fh.read())
            all_ok &= all(a == n for a, n in res.values())
            print(f"劇本 {sc + 1}: " + "  ".join(f"{k} {a}/{n}" for k, (a, n) in res.items()))
    print("OK" if all_ok else "MISMATCH")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
