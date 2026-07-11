"""Raised numbers, bank A (4..100): COM text sketch + exec-server extrude."""
import math
from pathlib import Path
import sys

import pythoncom
import win32com.client
from win32com.client import VARIANT, gencache

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "adapters" / "claude"))
import server as S

NULL_DISP = VARIANT(pythoncom.VT_DISPATCH, None)
mod = None
for info in gencache.GetGeneratedInfos():
    m = gencache.GetModuleForTypelib(*info)
    if hasattr(m, "IModelDoc2"):
        mod = m
        break

sw = win32com.client.GetActiveObject("SldWorks.Application")
doc = sw.ActiveDoc
assert "Bolt_Gauge" in str(doc.GetTitle), "gauge not active"
d2 = mod.IModelDoc2(doc._oleobj_)
ext = doc.Extension
sm = doc.SketchManager

# Close any sketch left open by earlier attempts
if sm.ActiveSketch is not None:
    sm.InsertSketch(True)
    print("closed dangling open sketch")

# 0. Delete junk sketches from the COM probing (ignore missing)
for junk in ("Sketch13", "Sketch14", "Sketch15", "Sketch16"):
    if ext.SelectByID2(junk, "SKETCH", 0, 0, 0, False, 0, NULL_DISP, 0):
        doc.EditDelete()
        print(f"deleted {junk}")
doc.ClearSelection2(True)

# 1. One sketch on the top face with all bank-A numbers
ok = ext.SelectByID2("", "FACE", -0.050, 0.008, -0.020, False, 0, NULL_DISP, 0)
print("face:", ok)
sm.InsertSketch(True)

for n in range(4, 101, 4):
    fin_center_x = (-(n) + 2.0) / 1000.0     # fin right of groove -n
    st = d2.InsertSketchText(fin_center_x - 0.0011, 0.0, -0.029,
                             str(n), 0, 0, 0, 1, 0)
    if st is None:
        print(f"text {n}: FAILED")
        continue
    stt = mod.ISketchText(st._oleobj_)
    fmt = stt.GetTextFormat()
    fmt.CharHeight = 0.0022
    fmt.Bold = True
    fmt.Escapement = math.pi / 2
    stt.SetTextFormat(False, fmt)
print("bank A texts inserted (sketch left open)")

# 2. Extrude via exec server (exits sketch mode itself, tracks the tree)
try:
    r = S._call("extrude_feature", {
        "depth": 0.0006, "feature_type": "boss", "angle": 360.0,
        "axis_x1": 0.0, "axis_y1": 0.0, "axis_x2": 0.0, "axis_y2": 0.001,
        "path_sketch": "", "profiles": "[]", "reverse": False,
        "through": False, "up_to_face_index": -1, "mid_plane": False})
    print("extrude:", r[:150])
except Exception as e:
    print("extrude failed:", str(e)[:200])
