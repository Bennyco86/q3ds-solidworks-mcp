"""Bolt gauge stage 3: M2-M10 clearance holes + save."""
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.environ.get("SOLIDPILOT_OUTPUT_DIR", str(REPO_ROOT / "outputs"))).expanduser()
sys.path.insert(0, str(REPO_ROOT / "adapters" / "claude"))
import server as S


def call(tool, **params):
    r = S._call(tool, params)
    print(f"== {tool} -> {r[:250]}")
    return r


MM = 0.001

# (label, clearance dia mm, cx mm, cy mm) — laid out top-to-bottom like the reference
HOLES = [
    ("M10", 11.0, 24, 30),
    ("M8",   9.0, 24, 15),
    ("M6",   6.6, 26, 2),
    ("M5",   5.5, 28, -10),
    ("M4",   4.5, 30, -20),
    ("M3",   3.4, 34, -28),
    ("M2",   2.4, 39, -35),
]

call("create_sketch", plane="Top Plane")
for label, dia, cx, cy in HOLES:
    call("add_sketch_entity", entity_type="circle",
         cx=cx*MM, cy=cy*MM, radius=dia/2*MM)
call("extrude_feature", feature_type="cut", through=True)

call("analyze_model", analysis_type="mass_properties")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
call("save_document", file_path=str(OUTPUT_DIR / "Q3DS_Bolt_Gauge.SLDPRT"))
