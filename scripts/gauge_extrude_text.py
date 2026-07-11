"""Extrude bank-A gauge numbers 0.6 mm via COM FeatureExtrusion3."""
from pathlib import Path
import re
import sys

import pythoncom
import win32com.client
from win32com.client import VARIANT, gencache

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "adapters" / "claude"))
import server as S

TARGET_SKETCH = "Sketch18"
JUNK_SKETCH = "Sketch17"
DEPTH_M = 0.0006
EXPECTED_MIN_MM3 = 15.0
EXPECTED_MAX_MM3 = 55.0

NULL_DISP = VARIANT(pythoncom.VT_DISPATCH, None)
mod = None
for info in gencache.GetGeneratedInfos():
    m = gencache.GetModuleForTypelib(*info)
    if hasattr(m, "IModelDoc2"):
        mod = m
        break

sw = win32com.client.GetActiveObject("SldWorks.Application")
doc = sw.ActiveDoc
assert "Bolt_Gauge" in str(doc.GetTitle)
ext = doc.Extension
sm = doc.SketchManager


def volume_mm3():
    result = S._call("analyze_model", {
        "analysis_type": "mass_properties",
        "name": "",
        "from_feature": "",
        "to_feature": "",
    })
    match = re.search(r"volume=([0-9.eE+-]+)", result)
    if not match:
        raise RuntimeError(f"Could not parse volume from: {result[:300]}")
    return float(match.group(1)) * 1e9


def close_open_sketch():
    if sm.ActiveSketch is not None:
        sm.InsertSketch(True)
        print("closed dangling open sketch")


close_open_sketch()

target = doc.FeatureByName(TARGET_SKETCH)
assert target is not None, f"{TARGET_SKETCH} not found"
print("target feature:", TARGET_SKETCH, "| type:", target.GetTypeName2)
assert "Sketch" in str(target.GetTypeName2) or "Profile" in str(target.GetTypeName2), \
    f"unexpected target feature type {target.GetTypeName2}"

fm = mod.IFeatureManager(doc.FeatureManager._oleobj_)
typed_doc = mod.IModelDoc2(doc._oleobj_)
before = volume_mm3()
print(
    f"before volume: {before:.2f} mm3 | expected bank-A text delta "
    f"{EXPECTED_MIN_MM3:.0f}..{EXPECTED_MAX_MM3:.0f} mm3"
)

doc.ClearSelection2(True)
ok = ext.SelectByID2(TARGET_SKETCH, "SKETCH", 0, 0, 0, False, 0, NULL_DISP, 0)
assert ok, f"failed to select {TARGET_SKETCH} for dissolve"
doc.EditSketch()
try:
    active = sm.ActiveSketch
    assert active is not None, f"failed to edit {TARGET_SKETCH}"
    sketch = mod.ISketch(active._oleobj_)
    text_segments = sketch.GetSketchTextSegments() or ()
    print(f"text segments before dissolve: {len(text_segments)}")
    dissolve_pass = 0
    while text_segments:
        previous_count = len(text_segments)
        dissolve_pass += 1
        doc.ClearSelection2(True)
        ext.SelectAll()
        typed_doc.DissolveSketchText()
        doc.ClearSelection2(True)
        text_segments = sketch.GetSketchTextSegments() or ()
        print(f"text segments after dissolve pass {dissolve_pass}: {len(text_segments)}")
        if len(text_segments) >= previous_count:
            raise RuntimeError(f"{TARGET_SKETCH} text dissolve did not make progress")
        if dissolve_pass > 40:
            raise RuntimeError(f"{TARGET_SKETCH} needed too many dissolve passes")
finally:
    close_open_sketch()

doc.ClearSelection2(True)
ok = ext.SelectByID2(TARGET_SKETCH, "SKETCH", 0, 0, 0, False, 0, NULL_DISP, 0)
print("sketch selected:", ok)
assert ok, f"failed to select {TARGET_SKETCH}"

# SolidWorks 2026 exposes the 23-arg FeatureExtrusion3 signature.
try:
    feat = fm.FeatureExtrusion3(
        True, False, False, 0, 0, DEPTH_M, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, True, True,
        0, 0.0, False)
finally:
    close_open_sketch()

if feat is None:
    raise RuntimeError("FeatureExtrusion3 returned null for bank-A text")

doc.EditRebuild3()
after = volume_mm3()
delta = after - before
print(f"extrusion feature: {feat.Name}")
print(f"after volume: {after:.2f} mm3 | delta {delta:.2f} mm3")
if delta < EXPECTED_MIN_MM3 or delta > EXPECTED_MAX_MM3:
    raise RuntimeError(
        f"Bank-A text volume delta {delta:.2f} mm3 outside expected "
        f"{EXPECTED_MIN_MM3:.0f}..{EXPECTED_MAX_MM3:.0f} mm3"
    )

doc.ClearSelection2(True)
if ext.SelectByID2(JUNK_SKETCH, "SKETCH", 0, 0, 0, False, 0, NULL_DISP, 0):
    doc.EditDelete()
    print(f"deleted leftover probe sketch: {JUNK_SKETCH}")
doc.ClearSelection2(True)

doc.Save3(1, 0, 0)
print("saved part")
