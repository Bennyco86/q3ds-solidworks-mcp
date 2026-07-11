"""Bolt gauge stage 4: drawing + PDF export for visual verification."""
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.environ.get("SOLIDPILOT_OUTPUT_DIR", str(REPO_ROOT / "outputs"))).expanduser()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO_ROOT / "adapters" / "claude"))
import server as S


def call(tool, **params):
    r = S._call(tool, params)
    print(f"== {tool} -> {r[:250]}")
    return r


PART = str(OUTPUT_DIR / "Q3DS_Bolt_Gauge.SLDPRT")

call("create_drawing", model_path=PART)
# A3 sheet is 420x297mm; top view (looking down on plate) center-left, iso right
call("add_drawing_view", view_type="top", pos_x=0.14, pos_y=0.17,
     scale=1.0, model_path=PART)
call("add_drawing_view", view_type="isometric", pos_x=0.32, pos_y=0.10,
     scale=1.0, model_path=PART)
call("export_document", format="PDF",
     file_path=str(OUTPUT_DIR / "Q3DS_Bolt_Gauge_check.pdf"))
