"""Bolt gauge v3 — single body, grooves as gaps in a raised top layer.

Only session-proven primitives: Top Plane multi-region bosses, Right Plane
blind cut (channel), Top Plane through-cuts (holes).
"""
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
BASE = 6.8 * MM     # plate below groove floors
FULL = 8 * MM       # full height of fins / head plate
GROOVE_W = 1.0      # mm
PITCH = 4.0         # mm


def call(tool, **params):
    r = S._call(tool, params)
    print(f"== {tool} -> {r[:150]}")
    return r


def volume_now():
    r = S._call("analyze_model", {"analysis_type": "mass_properties", "name": "",
                                  "from_feature": "", "to_feature": ""})
    return float(re.search(r"volume=([0-9.eE+-]+)", r).group(1))


def rect(x1, y1, x2, y2):
    call("add_sketch_entity", entity_type="rectangle",
         x1=x1*MM, y1=y1*MM, x2=x2*MM, y2=y2*MM)


def fin_spans(groove_centers, left=-106.0, right=0.0):
    """X spans of raised fins between 1mm grooves at the given centers."""
    spans = []
    prev = left
    for g in groove_centers:
        spans.append((prev, g - GROOVE_W / 2))
        prev = g + GROOVE_W / 2
    spans.append((prev, right))
    return spans


call("open_new_part")

# 1. Base plate 6.8mm: comb + head as two regions in one sketch
call("create_sketch", plane="Top Plane")
rect(-106, -32, 0, 32)
rect(0, -45, 48, 45)
call("extrude_feature", depth=BASE, feature_type="boss")
print(f"base volume: {volume_now()*1e9:.0f} mm3")

# 2. Top layer to 8mm: head plate + fins (grooves = the gaps)
grooves_a = [-100 + 4 * k for k in range(25)]   # lengths 100..4
grooves_b = [-98 + 4 * k for k in range(24)]    # lengths 98..6
call("create_sketch", plane="Top Plane")
rect(0, -45, 48, 45)
for x1, x2 in fin_spans(grooves_a):
    rect(x1, 7, x2, 32)       # bank A (sketch +y)
for x1, x2 in fin_spans(grooves_b):
    rect(x1, -32, x2, -7)     # bank B
call("extrude_feature", depth=FULL, feature_type="boss")
v = volume_now()
print(f"after top layer: {v*1e9:.0f} mm3")

# 3. Tapered channel: trapezoid on Right Plane, blind cut along comb
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

# 4. Gauge holes M10..M2
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
