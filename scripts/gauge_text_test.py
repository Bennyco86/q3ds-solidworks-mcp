"""COM test: one raised sketch-text on the gauge's top face."""
import pythoncom
import win32com.client
from win32com.client import VARIANT

NULL_DISP = VARIANT(pythoncom.VT_DISPATCH, None)

sw = win32com.client.GetActiveObject("SldWorks.Application")
doc = sw.ActiveDoc
print("active doc:", doc.GetTitle)

if "Bolt_Gauge" not in str(doc.GetTitle):
    raise SystemExit("gauge is not the active doc — aborting")

ext = doc.Extension
sm = doc.SketchManager

# Select a fin top face (fin at X -99.5..-96.5, bank A model Z -7..-32, Y=8mm)
ok = ext.SelectByID2("", "FACE", -0.098, 0.008, -0.020, False, 0, NULL_DISP, 0)
print("face selected:", ok)
sm.InsertSketch(True)

# InsertSketchText(x, y, z, text, alignment, flip, rotate, widthFactor?...)
# Try the documented 8-arg form first.
try:
    st = sm.InsertSketchText(-0.0985, 0.010, 0.0, "100", 0, 0, 0, 1)
    print("InsertSketchText(8 args):", st)
except Exception as e:
    print("8-arg failed:", e)
    st = None

if st is None:
    try:
        st = sm.InsertSketchText(-0.0985, 0.010, 0.0, "100", 0, 0, 0, 1, 0)
        print("InsertSketchText(9 args):", st)
    except Exception as e:
        print("9-arg failed:", e)

doc.SketchManager.InsertSketch(True)  # exit sketch
print("sketch closed")
