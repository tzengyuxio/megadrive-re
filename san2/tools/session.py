"""Key sequences of MD 三國志II and a helper that plays one in MAME and returns the memory dumps taken at each
@tag (tools/drive.py syntax; tags dump RAM / VRAM / CRAM / VSRAM / regs).

Sequences (frame timings found with tools/drive.py; the Y/N answer is ← for Y, → for N; number prompts
start at "00" with the cursor on the tens digit):
  BOOT       title → scenario list (scenario 1 highlighted)
  scenario(k) BOOT + pick scenario k (0-5) → "何人でプレイしますか" (scenario data loaded)
  MAP        scenario(0) + 1 player → the big map where the ruler is picked
  RULER      MAP + C on the first ruler (袁術): his face, "(Y/N)?"
  COMMAND    RULER + Y, level 1, watch wars, settings OK, skip the openings → 袁術's command menu (荊州 19)
  WAR_MAP    COMMAND + 軍事 → 戦争: the big map, "どこへ せめこみますか"
  BATTLE     COMMAND + 軍事 → 戦争 → province 20 (劉表) with 袁術 alone, no gold, 20 food, 袁胤 left as
             governor → battle field 20, "袁術を はいちしてください" (deployment)
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
from drive import events_lua, schedule
from mame import run

BOOT = "w900 start:10 w400 start:30 w200"


def scenario(k: int) -> str:
    return BOOT + " down:4 w20" * k + " c:10 w300"


MAP = scenario(0) + " right:2 w30 up:2 w30 c:10 w200"
RULER = MAP + " c:10 w200"
COMMAND = RULER + (" left:6 w300 up:2 w30 c:10 w300 left:6 w300 left:6 w300 c:6 w300 c:6 w300 b:6 w300"
                   " c:6 w300 c:6 w300 b:6 w300")
WAR_MAP = COMMAND + " right:6 w60 c:6 w100 down:6*3 w30 c:6 w150"  # 軍事, 戦争
BATTLE = WAR_MAP + (" left:6 w30 c:6 w150"  # province 20
                    " c:6 w60 right:6 w30 down:6*2 w30 c:6 w150"  # 袁術 only, 終了
                    " w150 c:6 w150 right:6 w20 up:6*2 w20 c:6 w200"  # gold 0, food 20
                    " left:6 w300 c:6 w300")  # attack: Y; governor: first in the list


def play(rom: str, steps: str, extra_lua: str = "", debug: bool = False) -> dict[str, dict[str, bytes]]:
    """Play steps; return {tag: {"ram", "vram", "cram", "vsram", "regs", "png"}} for every @tag."""
    events, end = schedule(steps.split())
    tags = [v for _, k, v in events if k == "shot"]
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "s")
        run(rom, extra_lua + events_lua(events, out, end, True), debug=debug)
        res = {}
        for t in tags:
            res[t] = {}
            for ext in ("ram", "vram", "cram", "vsram", "regs", "png"):
                with open(f"{out}_{t}.{ext}", "rb") as fh:
                    res[t][ext] = fh.read()
        return res
