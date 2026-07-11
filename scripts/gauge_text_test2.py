"""COM test 2: typed dispatch for InsertSketchText."""
import pythoncom
import win32com.client
from win32com.client import VARIANT, gencache

NULL_DISP = VARIANT(pythoncom.VT_DISPATCH, None)

sw = win32com.client.GetActiveObject("SldWorks.Application")
doc = sw.ActiveDoc
title = doc.GetTitle
print("active doc:", title)
if "Bolt_Gauge" not in str(title):
    raise SystemExit("gauge not active — aborting")

ext = doc.Extension
sm = win32com.client.CastTo(doc.SketchManager, "ISketchManager")
print("sketch manager cast:", type(sm).__name__)

ok = ext.SelectByID2("", "FACE", -0.098, 0.008, -0.020, False, 0, NULL_DISP, 0)
print("face selected:", ok)
sm.InsertSketch(True)

st = sm.InsertSketchText(-0.0985, 0.010, 0.0, "100", 0, 0, 0, 1)
print("InsertSketchText:", st)
if st is not None:
    fmt = st.GetTextFormat()
    fmt.CharHeight = 0.0025   # 2.5mm characters
    fmt.Bold = True
    r = st.SetTextFormat(False, fmt)
    print("text format set:", r)

sm.InsertSketch(True)
print("sketch closed; sketch text OK")
