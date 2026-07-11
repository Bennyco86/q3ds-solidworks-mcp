"""Unit tests for adapter-side batching and compact inspection helpers."""

import json
import os
import sys
import unittest
from unittest.mock import patch


_HERE = os.path.dirname(os.path.abspath(__file__))
_ADAPTER_DIR = os.path.dirname(_HERE)
sys.path.insert(0, _ADAPTER_DIR)

import server  # noqa: E402


def _completed(*, state=1, sketch=None, features=None, geometry=None):
    return {
        "status": "COMPLETED",
        "stateVersion": state,
        "cadState": {
            "activeDocument": "Part1",
            "activeSketch": sketch,
            "features": features or [],
        },
        "result_geometry": geometry,
    }


class OrchestrationTests(unittest.TestCase):
    def test_batch_resolves_previous_result(self):
        calls = []

        def fake_call(tool, params):
            calls.append((tool, params))
            if tool == "create_sketch":
                return _completed(state=1, sketch="Sketch7")
            return _completed(state=2, features=["RenamedSketch"])

        with patch.object(server, "_call_raw", fake_call):
            payload = json.loads(server.execute_batch([
                {"tool": "create_sketch", "params": {"plane": "Top Plane"}},
                {"tool": "edit_feature", "params": {
                    "feature_name": "$0.sketch", "action": "rename", "new_name": "Profile",
                }},
            ]))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["completed"], 2)
        self.assertEqual(calls[1][1]["feature_name"], "Sketch7")

    def test_batch_stops_after_failure(self):
        responses = iter([
            _completed(state=1),
            {
                "status": "FAILED",
                "stateVersion": 1,
                "error": {"code": "BAD", "message": "nope"},
            },
        ])
        calls = []

        def fake_call(tool, params):
            calls.append(tool)
            return next(responses)

        with patch.object(server, "_call_raw", fake_call):
            payload = json.loads(server.execute_batch([
                {"tool": "verify_state", "params": {}},
                {"tool": "bad_tool", "params": {}},
                {"tool": "verify_state", "params": {}},
            ]))

        self.assertFalse(payload["ok"])
        self.assertTrue(payload["stopped"])
        self.assertEqual(calls, ["verify_state", "bad_tool"])
        self.assertEqual(payload["results"][1]["code"], "BAD")

    def test_feature_tree_summary_is_compact(self):
        recipe = {
            "feature_count": 3,
            "features": [
                {"name": "Sketch1", "type": "ProfileFeature"},
                {"name": "Boss-Extrude1", "type": "ICE"},
                {"name": "Fillet1", "type": "Fillet"},
            ],
        }
        summary = server._feature_tree_summary(_completed(features=[json.dumps(recipe)]))

        self.assertEqual(summary, {
            "feature_count": 3,
            "names": ["Sketch1", "Boss-Extrude1", "Fillet1"],
            "types": {"ProfileFeature": 1, "ICE": 1, "Fillet": 1},
        })


class AssemblyOrchestrationTests(unittest.TestCase):
    def test_inspect_model_assembly_path(self):
        asm_root = {
            "component_count": 2,
            "components": [
                {"name": "base-1", "suppression": "resolved", "fixed": True,
                 "configuration": "Default", "path": "C:\\base.sldprt"},
                {"name": "top-1", "suppression": "lightweight", "fixed": False,
                 "configuration": "Default", "path": "C:\\top.sldprt"},
            ],
            "mate_count": 1,
            "mates": [{"feature": "Coincident1", "type": "coincident"}],
        }

        def fake_call(tool, params):
            if tool == "verify_state":
                resp = _completed()
                resp["cadState"]["documentType"] = "ASSEMBLY"
                resp["cadState"]["activeDocument"] = "Assem1"
                return resp
            if tool == "analyze_assembly":
                self.assertFalse(params["include_faces"])
                return _completed(features=[json.dumps(asm_root)])
            if tool == "analyze_model":
                self.assertEqual(params["analysis_type"], "mass_properties")
                return _completed(features=["volume=1E-05", "mass=0.01"])
            raise AssertionError(f"unexpected tool {tool}")

        with patch.object(server, "_call_raw", fake_call):
            out = server.inspect_model(include_visual=False)

        payload = json.loads(out[0].text)
        self.assertEqual(payload["document_type"], "ASSEMBLY")
        self.assertEqual(payload["assembly"]["component_count"], 2)
        self.assertEqual(payload["assembly"]["mate_count"], 1)
        self.assertEqual(payload["assembly"]["components"][0]["name"], "base-1")
        # compact view: full file paths are trimmed from the component summary
        self.assertNotIn("path", payload["assembly"]["components"][0])
        self.assertEqual(payload["mass"]["volume"], 1e-05)

    def test_add_assembly_mate_passes_refs(self):
        seen = {}

        def fake_call(tool, params):
            seen["tool"] = tool
            seen["params"] = params
            return '{"ok":true}'

        with patch.object(server, "_call", fake_call):
            server.add_assembly_mate(
                mate_type="distance", face_ref1="QUJD", face_ref2="REVG",
                distance=0.005, alignment="anti_aligned")

        self.assertEqual(seen["tool"], "add_assembly_mate")
        self.assertEqual(seen["params"]["mate_type"], "distance")
        self.assertEqual(seen["params"]["face_ref1"], "QUJD")
        self.assertEqual(seen["params"]["face_ref2"], "REVG")
        self.assertEqual(seen["params"]["distance"], 0.005)
        self.assertEqual(seen["params"]["alignment"], "anti_aligned")

    def test_insert_component_fixed_tristate(self):
        seen = {}

        def fake_call(tool, params):
            seen["params"] = params
            return '{"ok":true}'

        with patch.object(server, "_call", fake_call):
            server.insert_component(file_path="C:\\base.sldprt")
        # omitted fixed must NOT be sent — preserves SolidWorks' first-component grounding
        self.assertNotIn("fixed", seen["params"])

        with patch.object(server, "_call", fake_call):
            server.insert_component(file_path="C:\\base.sldprt", fixed=True)
        self.assertIs(seen["params"]["fixed"], True)

        with patch.object(server, "_call", fake_call):
            server.insert_component(file_path="C:\\base.sldprt", fixed=False)
        self.assertIs(seen["params"]["fixed"], False)


if __name__ == "__main__":
    unittest.main()
