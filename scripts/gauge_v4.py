"""Bolt gauge v4 — single body; every boss is a single rectangle; fins via
boss seed + linear pattern (all primitives individually proven this session)."""
import json
import os
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.environ.get("SOLIDPILOT_OUTPUT_DIR", str(REPO_ROOT / "outputs"))).expanduser()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO_ROOT / "adapters" / "claude"))
import server as S

MM = 0.001


def call(tool, **params):
    r = S._call(tool, params)
    print(f"== {tool} -> {r[:130]}")
    return r


def volume_now():
    r = S._call("analyze_model", {"analysis_type": "mass_properties", "name": "",
                                  "from_feature": "", "to_feature": ""})
    return float(re.search(r"volume=([0-9.eE+-]+)", r).group(1))


def boss_rect(x1, y1, x2, y2, depth_mm):
    call("create_sketch", plane="Top Plane")
    call("add_sketch_entity", entity_type="rectangle",
         x1=x1*MM, y1=y1*MM, x2=x2*MM, y2=y2*MM)
    r = call("extrude_feature", depth=depth_mm*MM, feature_type="boss")
    return re.search(r"features=\['([^']+)'\]", r).group(1)


call("open_new_part")

# 1. Comb base 6.8mm + head plate 8mm
boss_rect(-106, -32, 0, 32, 6.8)
boss_rect(0, -45, 48, 45, 8.0)

# 2. Bank A fins (top layer 8mm; grooves at centers -100..-4)
feat = boss_rect(-99.5, 7, -96.5, 32, 8.0)          # seed fin
call("create_pattern", pattern_type="linear", feature_name=feat,
     spacing=4*MM, count=24, direction="X")
boss_rect(-106, 7, -100.5, 32, 8.0)                 # left end block
boss_rect(-3.5, 7, 0, 32, 8.0)                      # right end fin

# 3. Bank B fins (grooves at centers -98..-6)
feat = boss_rect(-97.5, -32, -94.5, -7, 8.0)
call("create_pattern", pattern_type="linear", feature_name=feat,
     spacing=4*MM, count=23, direction="X")
boss_rect(-106, -32, -98.5, -7, 8.0)
boss_rect(-5.5, -32, 0, -7, 8.0)

v = volume_now()
print(f"plate with fins: {v*1e9:.0f} mm3 (expect ~85574)")

# 4. Tapered channel from Right Plane (proven blind cut)
r = call("create_sketch", plane="Right Plane")
frame = json.loads(re.search(r"result_geometry=(\{.*)$", r, re.DOTALL).group(1))["frame"]


def to_sketch(p):
    o, xd, yd = frame["origin"], frame["xdir"], frame["ydir"]
    d = [p[0]-o[0], p[1]-o[1], p[2]-o[2]]
    return (sum(d[i]*xd[i] for i in range(3)), sum(d[i]*yd[i] for i in range(3)))


trap = [(0.0, 8.5*MM, -7*MM), (0.0, 8.5*MM, 7*MM),
        (0.0, 2*MM, 1.5*MM), (0.0, 2*MM, -1.5*MM)]
pts = [to_sketch(p) for p in trap]
for i in range(4):
    a, b = pts[i], pts[(i+1) % 4]
    call("add_sketch_entity", entity_type="line",
         x1=a[0], y1=a[1], x2=b[0], y2=b[1])
call("extrude_feature", feature_type="cut", depth=107*MM)
v2 = volume_now()
print(f"channel removed {(v-v2)*1e9:.0f} mm3")

# 5. Gauge holes
HOLES = [(11.0, 24, 30), (9.0, 24, 15), (6.6, 26, 2), (5.5, 28, -10),
         (4.5, 30, -20), (3.4, 34, -28), (2.4, 39, -35)]
call("create_sketch", plane="Top Plane")
for dia, cx, cy in HOLES:
    call("add_sketch_entity", entity_type="circle",
         cx=cx*MM, cy=cy*MM, radius=dia/2*MM)
call("extrude_feature", feature_type="cut", through=True)

r = call("analyze_model", analysis_type="geometry")
print("FINAL:", r[:180])
call("save_document",
     file_path=str(OUTPUT_DIR / "Q3DS_Bolt_Gauge_v2.SLDPRT"))
