"""Bolt gauge v2 stage B2: grooves via offset reference plane + holes + save."""
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
    print(f"== {tool} -> {r[:180]}")
    return r


def volume_now():
    r = S._call("analyze_model", {"analysis_type": "mass_properties", "name": "",
                                  "from_feature": "", "to_feature": ""})
    m = re.search(r"volume=([0-9.eE+-]+)", r)
    return float(m.group(1))


# 0. Force-exit any dangling open sketch (extrude exits sketch mode first,
#    then fails harmlessly on the open profile).
try:
    call("extrude_feature", feature_type="cut", depth=0.0001)
except Exception as e:
    print(f"(sketch-mode cleanup: {str(e)[:120]})")

v = volume_now()
print(f"start volume: {v*1e9:.0f} mm3")

# 1. Reference plane at the top surface
r = call("add_reference_geometry", type="plane",
         ref_plane_name="Top Plane", offset=8*MM)
plane_name = re.search(r"features=\['([^']+)'\]", r).group(1)
print(f"top surface plane: {plane_name}")


def groove_cut(x_lo_mm, x_hi_mm, y_lo_mm, y_hi_mm, reverse):
    call("create_sketch", plane=plane_name)
    call("add_sketch_entity", entity_type="rectangle",
         x1=x_lo_mm*MM, y1=y_lo_mm*MM, x2=x_hi_mm*MM, y2=y_hi_mm*MM)
    return call("extrude_feature", feature_type="cut", depth=1.2*MM,
                reverse=reverse)


# 2. Discover cut direction with the first seed groove (bank A, model -Z side
#    = sketch +y). Try reverse=True first (down into the plate is the reverse
#    of the plane normal in most SW configs); fall back to reverse=False.
GROOVE_MM3 = 1.0 * 25.0 * 1.2
seed_feat_a = None
for rev in (True, False):
    try:
        r = groove_cut(-100.5, -99.5, 8, 33, rev)
        v2 = volume_now()
        if v - v2 > GROOVE_MM3 * 0.5e-9:
            seed_feat_a = re.search(r"features=\['([^']+)'\]", r).group(1)
            print(f"groove direction reverse={rev} works; removed {(v-v2)*1e9:.0f} mm3")
            v = v2
            break
        print(f"reverse={rev}: no material removed, trying other direction")
    except Exception as e:
        print(f"reverse={rev} failed: {str(e)[:120]}")

assert seed_feat_a, "could not establish groove direction"
REV = rev

call("create_pattern", pattern_type="linear", feature_name=seed_feat_a,
     spacing=4*MM, count=25, direction="X")
v2 = volume_now()
print(f"bank A patterned: removed {(v-v2)*1e9:.0f} mm3 (expect ~{GROOVE_MM3*24:.0f})")
v = v2

# 3. Bank B seed + pattern (model +Z side = sketch -y), lengths 6..98
r = groove_cut(-98.5, -97.5, -33, -8, REV)
seed_feat_b = re.search(r"features=\['([^']+)'\]", r).group(1)
call("create_pattern", pattern_type="linear", feature_name=seed_feat_b,
     spacing=4*MM, count=24, direction="X")
v2 = volume_now()
print(f"bank B patterned: removed {(v-v2)*1e9:.0f} mm3 (expect ~{GROOVE_MM3*24:.0f})")
v = v2

# 4. Gauge holes
HOLES = [(11.0, 24, 30), (9.0, 24, 15), (6.6, 26, 2), (5.5, 28, -10),
         (4.5, 30, -20), (3.4, 34, -28), (2.4, 39, -35)]
call("create_sketch", plane="Top Plane")
for dia, cx, cy in HOLES:
    call("add_sketch_entity", entity_type="circle",
         cx=cx*MM, cy=cy*MM, radius=dia/2*MM)
call("extrude_feature", feature_type="cut", through=True)
v2 = volume_now()
print(f"holes: removed {(v-v2)*1e9:.0f} mm3 (expect ~1969)")

r = call("analyze_model", analysis_type="geometry")
print("FINAL:", r[:200])
call("save_document",
     file_path=str(OUTPUT_DIR / "Q3DS_Bolt_Gauge_v2.SLDPRT"))
