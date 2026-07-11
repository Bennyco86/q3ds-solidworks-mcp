"""Bolt gauge v2 stage B: shallow graduation grooves on the top face + holes + save."""
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
    print(f"== {tool} -> {r[:200]}")
    return r


def geometry_of(resp):
    m = re.search(r"result_geometry=(\{.*)$", resp, re.DOTALL)
    return json.loads(m.group(1)) if m else {}


def to_sketch(frame, p):
    o, xd, yd = frame["origin"], frame["xdir"], frame["ydir"]
    d = [p[0] - o[0], p[1] - o[1], p[2] - o[2]]
    return (sum(d[i] * xd[i] for i in range(3)),
            sum(d[i] * yd[i] for i in range(3)))


# --- find the top face (planar, normal +Y, large area) ---
r = S._call("analyze_model", {"analysis_type": "faces", "name": "",
                              "from_feature": "", "to_feature": ""})
m = re.search(r"features=\['(.*)'\]", r, re.DOTALL)
faces = json.loads(m.group(1)).get("faces", [])
top = None
for f in faces:
    n = f.get("normal")
    if n and abs(n[1] - 1.0) < 0.01 and f.get("area", 0) > 0.004:
        top = f
        break
print(f"top face: index={top['i']} area={top.get('area')} point={top.get('point')}")


def groove_bank(seed_center_x_mm, z_sign, count):
    """One bank: seed groove + linear pattern. z_sign: -1 or +1 model-Z side."""
    r = call("create_sketch", on_face=True, face_index=top["i"])
    frame = geometry_of(r)["frame"]
    x1, xc = (seed_center_x_mm - 0.5) * MM, (seed_center_x_mm + 0.5) * MM
    zA, zB = z_sign * 8 * MM, z_sign * 33 * MM
    corners = [
        (x1, 8*MM, zA), (xc, 8*MM, zA), (xc, 8*MM, zB), (x1, 8*MM, zB),
    ]
    pts = [to_sketch(frame, p) for p in corners]
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        call("add_sketch_entity", entity_type="line",
             x1=a[0], y1=a[1], x2=b[0], y2=b[1])
    r = call("extrude_feature", feature_type="cut", depth=1.2*MM)
    feat = re.search(r"features=\['([^']+)'\]", r).group(1)
    call("create_pattern", pattern_type="linear", feature_name=feat,
         spacing=4*MM, count=count, direction="X")


groove_bank(-100, -1, 25)   # lengths 4..100 bank
groove_bank(-98, +1, 24)    # lengths 6..98 bank

r = call("analyze_model", analysis_type="mass_properties")
print("after grooves:", r[:220])

# --- gauge holes (Top Plane through-cut, proven in v1) ---
HOLES = [(11.0, 24, 30), (9.0, 24, 15), (6.6, 26, 2), (5.5, 28, -10),
         (4.5, 30, -20), (3.4, 34, -28), (2.4, 39, -35)]
call("create_sketch", plane="Top Plane")
for dia, cx, cy in HOLES:
    call("add_sketch_entity", entity_type="circle",
         cx=cx*MM, cy=cy*MM, radius=dia/2*MM)
call("extrude_feature", feature_type="cut", through=True)

r = call("analyze_model", analysis_type="geometry")
print("FINAL GEOMETRY:", r[:250])
call("save_document",
     file_path=str(OUTPUT_DIR / "Q3DS_Bolt_Gauge_v2.SLDPRT"))
