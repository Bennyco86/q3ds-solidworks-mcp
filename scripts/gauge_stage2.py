"""Bolt gauge stage 2: teeth slot seeds + linear patterns.

Top bank: slots at X centers -100..-4 step 4 (lengths 100..4)
Bottom bank: slots at X centers -98..-6 step 4 (lengths 98..6)
Slot width 2mm, cut through; seeds at far LEFT, pattern direction X (+).
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "adapters" / "claude"))
import server as S


def call(tool, **params):
    r = S._call(tool, params)
    print(f"== {tool} -> {r[:300]}")
    return r


MM = 0.001

# Top bank seed slot: center X=-100, Y from 5.5 past outer edge
call("create_sketch", plane="Top Plane")
call("add_sketch_entity", entity_type="rectangle",
     x1=-101*MM, y1=5.5*MM, x2=-99*MM, y2=34*MM)
call("extrude_feature", feature_type="cut", through=True)  # -> Cut-Extrude2

call("create_pattern", pattern_type="linear", feature_name="Cut-Extrude2",
     spacing=4*MM, count=25, direction="X")

call("analyze_model", analysis_type="mass_properties")

# Bottom bank seed slot: center X=-98
call("create_sketch", plane="Top Plane")
call("add_sketch_entity", entity_type="rectangle",
     x1=-99*MM, y1=-34*MM, x2=-97*MM, y2=-5.5*MM)
call("extrude_feature", feature_type="cut", through=True)  # -> Cut-Extrude3

call("create_pattern", pattern_type="linear", feature_name="Cut-Extrude3",
     spacing=4*MM, count=24, direction="X")

call("analyze_model", analysis_type="mass_properties")
