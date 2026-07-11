"""Bolt gauge v2 stage A: one solid body — comb boss, tapered channel, head plate.

Order matters: channel is cut while only the comb boss (X<0) exists, so if the
cut direction guess is wrong it removes nothing (detectable, harmless) instead
of carving the head plate.
"""
import json
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "adapters" / "claude"))
import server as S

MM = 0.001


def call(tool, **params):
    r = S._call(tool, params)
    print(f"== {tool} -> {r[:220]}")
    return r


def geometry_of(resp):
    m = re.search(r"result_geometry=(\{.*)$", resp, re.DOTALL)
    return json.loads(m.group(1)) if m else {}


def volume_of(resp):
    g = geometry_of(resp)
    return g.get("volume")


def to_sketch_coords(frame, p):
    """Model-space point -> 2D sketch coords using the sketch frame."""
    o, xd, yd = frame["origin"], frame["xdir"], frame["ydir"]
    d = [p[0] - o[0], p[1] - o[1], p[2] - o[2]]
    sx = sum(d[i] * xd[i] for i in range(3))
    sy = sum(d[i] * yd[i] for i in range(3))
    return sx, sy


# Fresh part; v1 stays open in SW until Benny closes it (different doc).
call("open_new_part")

# 1. Comb boss only: X -106..0, width 64 (sketch-y +-32), 8mm thick (model Y 0..8)
call("create_sketch", plane="Top Plane")
call("add_sketch_entity", entity_type="rectangle",
     x1=-106*MM, y1=-32*MM, x2=0.0, y2=32*MM)
r = call("extrude_feature", depth=8*MM, feature_type="boss")
v0 = volume_of(r)
print(f"comb volume: {v0}")

# 2. Tapered channel: trapezoid on Right Plane, cut 107mm along the comb.
#    Model coords: top opening 14mm wide at Y=8 (surface), floor 3mm wide at Y=2.
r = call("create_sketch", plane="Right Plane")
frame = geometry_of(r)["frame"]
print(f"right plane frame: {frame}")
trap_model = [
    (0.0, 8.5*MM, -7*MM),   # above surface, left
    (0.0, 8.5*MM, 7*MM),    # above surface, right
    (0.0, 2*MM, 1.5*MM),    # floor right
    (0.0, 2*MM, -1.5*MM),   # floor left
]
pts = [to_sketch_coords(frame, p) for p in trap_model]
for i in range(4):
    x1, y1 = pts[i]
    x2, y2 = pts[(i + 1) % 4]
    call("add_sketch_entity", entity_type="line", x1=x1, y1=y1, x2=x2, y2=y2)

r = call("extrude_feature", feature_type="cut", depth=107*MM)
v1 = volume_of(r)
print(f"after channel try 1: {v1}")
if v1 is not None and v0 is not None and abs(v1 - v0) < 1e-9:
    print("channel cut went the wrong way (no material removed) — need reverse")
    # The cut feature exists but removed nothing; add the reversed cut.
    r = call("create_sketch", plane="Right Plane")
    frame = geometry_of(r)["frame"]
    pts = [to_sketch_coords(frame, p) for p in trap_model]
    for i in range(4):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % 4]
        call("add_sketch_entity", entity_type="line", x1=x1, y1=y1, x2=x2, y2=y2)
    r = call("extrude_feature", feature_type="cut", depth=107*MM, reverse=True)
    print(f"after channel try 2: {volume_of(r)}")

# 3. Head plate boss: X 0..48, sketch-y +-45
call("create_sketch", plane="Top Plane")
call("add_sketch_entity", entity_type="rectangle",
     x1=0.0, y1=-45*MM, x2=48*MM, y2=45*MM)
r = call("extrude_feature", depth=8*MM, feature_type="boss")
print(f"after head plate: {volume_of(r)}")

r = call("analyze_model", analysis_type="geometry")
print("GEOMETRY (must be 1 body):", r[:300])
