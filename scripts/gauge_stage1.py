"""Bolt gauge stage 1: new part, T-plate bosses, central channel cut."""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "adapters" / "claude"))
import server as S


def call(tool, **params):
    r = S._call(tool, params)
    print(f"== {tool} -> {r[:400]}")
    return r


MM = 0.001

call("open_new_part")

# Head plate: X 0..48, Y -45..45, 8mm thick
call("create_sketch", plane="Top Plane")
call("add_sketch_entity", entity_type="rectangle",
     x1=0.0, y1=-45*MM, x2=48*MM, y2=45*MM)
call("extrude_feature", depth=8*MM, feature_type="boss")

# Comb tail: X -106..0, Y -32..32
call("create_sketch", plane="Top Plane")
call("add_sketch_entity", entity_type="rectangle",
     x1=-106*MM, y1=-32*MM, x2=0.0, y2=32*MM)
call("extrude_feature", depth=8*MM, feature_type="boss")

# Central channel: 11mm wide, open at left end (overhang past edge)
call("create_sketch", plane="Top Plane")
call("add_sketch_entity", entity_type="rectangle",
     x1=-108*MM, y1=-5.5*MM, x2=0.0, y2=5.5*MM)
call("extrude_feature", feature_type="cut", through=True)

call("analyze_model", analysis_type="mass_properties")
