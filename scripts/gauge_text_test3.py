"""COM test 3: wrap raw IDispatch in the makepy-generated typed classes."""
import pythoncom
import win32com.client
from win32com.client import VARIANT, gencache

NULL_DISP = VARIANT(pythoncom.VT_DISPATCH, None)

infos = list(gencache.GetGeneratedInfos())
print("generated typelibs:", infos)
mod = None
for clsid, lcid, major, minor in infos:
    m = gencache.GetModuleForTypelib(clsid, lcid, major, minor)
    if hasattr(m, "ISketchManager"):
        mod = m
        print("found ISketchManager in", m.__name__)
        break
assert mod, "no generated module with ISketchManager"

sw = win32com.client.GetActiveObject("SldWorks.Application")
doc = sw.ActiveDoc
print("active doc:", doc.GetTitle)
if "Bolt_Gauge" not in str(doc.GetTitle):
    raise SystemExit("gauge not active — aborting")

ext = doc.Extension
sm = mod.ISketchManager(doc.SketchManager._oleobj_)
print("typed sketch manager OK")

ok = ext.SelectByID2("", "FACE", -0.098, 0.008, -0.020, False, 0, NULL_DISP, 0)
print("face selected:", ok)
sm.InsertSketch(True)

st = sm.InsertSketchText(-0.0985, 0.010, 0.0, "100", 0, 0, 0, 1)
print("InsertSketchText ->", st)
if st is not None:
    st2 = mod.ISketchText(st._oleobj_) if not hasattr(st, "GetTextFormat") else st
    fmt = st2.GetTextFormat()
    fmt.CharHeight = 0.0025
    fmt.Bold = True
    print("set format:", st2.SetTextFormat(False, fmt))

sm.InsertSketch(True)
print("DONE — text sketch created")
