"""Unit tests for the SolidWorks Simulation MCP adapter boundary."""

import json
import os
import sys
import unittest
from unittest.mock import patch


_HERE = os.path.dirname(os.path.abspath(__file__))
_ADAPTER_DIR = os.path.dirname(_HERE)
sys.path.insert(0, _ADAPTER_DIR)

import server  # noqa: E402


class SimulationCoordinateTests(unittest.TestCase):
    def test_parse_face_coordinates_normalizes_numbers(self):
        result = server._parse_face_coordinates(
            '[{"x":1,"y":0.25,"z":-2}]', "faces")

        self.assertEqual(result, [{"x": 1.0, "y": 0.25, "z": -2.0}])

    def test_parse_face_coordinates_rejects_invalid_shapes_and_values(self):
        invalid_values = [
            "not-json",
            "{}",
            "[]",
            '[{"x":1,"y":2}]',
            '[{"x":1,"y":2,"z":3,"label":"top"}]',
            '[{"x":true,"y":2,"z":3}]',
            '[{"x":1e999,"y":2,"z":3}]',
        ]

        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                server._parse_face_coordinates(value, "faces")

    def test_parse_face_coordinates_allows_empty_preserved_faces(self):
        self.assertEqual(
            server._parse_face_coordinates("[]", "preserved_faces", allow_empty=True),
            [],
        )


class SimulationToolTests(unittest.TestCase):
    def test_add_fixture_passes_parsed_faces_to_execution(self):
        with patch.object(server, "_call", return_value='{"ok":true}') as call:
            result = server.sim_add_fixture(
                study_name="Static_Study",
                faces='[{"x":0.051,"y":0,"z":-0.092}]',
            )

        self.assertEqual(result, '{"ok":true}')
        call.assert_called_once_with(
            "sim_add_fixture",
            {
                "study_name": "Static_Study",
                "faces": [{"x": 0.051, "y": 0.0, "z": -0.092}],
            },
        )

    def test_get_results_passes_user_yield_strength(self):
        with patch.object(server, "_call", return_value='{"ok":true}') as call:
            server.sim_get_results("Static_Study", yield_strength_pa=50_000_000)

        call.assert_called_once_with(
            "sim_get_results",
            {"study_name": "Static_Study", "yield_strength_pa": 50_000_000},
        )

    def test_topology_setup_parses_preserved_faces(self):
        faces = [
            {"x": 0.051, "y": 0.0, "z": -0.092},
            {"x": 0.051, "y": 0.010, "z": -0.023},
        ]
        with patch.object(server, "_call", return_value='{"ok":true}') as call:
            server.sim_topology_setup(
                study_name="Topology_Study",
                mass_reduction_percent=50,
                preserved_faces=json.dumps(faces),
                min_thickness=0.003,
            )

        call.assert_called_once_with(
            "sim_topology_setup",
            {
                "study_name": "Topology_Study",
                "goal": "best_stiffness",
                "mass_reduction_percent": 50,
                "preserved_faces": faces,
                "min_thickness": 0.003,
            },
        )


if __name__ == "__main__":
    unittest.main()
