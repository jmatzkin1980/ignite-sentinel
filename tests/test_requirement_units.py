import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.discovery import extract_requirement_units, ingest


class RequirementUnitsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp())
        self.old_cwd = Path.cwd()
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_extracts_named_units_with_cited_mentions(self) -> None:
        text = "Necesitamos un dashboard con cards de metricas. El login usa roles y permisos."

        units = extract_requirement_units(text, "RAW-001", Path("input.md"))

        self.assertGreaterEqual(len(units), 3)
        self.assertEqual([unit["id"] for unit in units], [f"RU-{index:03d}" for index in range(1, len(units) + 1)])
        mentions = {unit["evidence_mention"].lower() for unit in units}
        self.assertIn("dashboard", mentions)
        self.assertIn("login", mentions)
        self.assertTrue({"roles", "permisos"} & mentions)
        self.assertTrue(all(unit["source"] == "input.md" for unit in units))

    def test_does_not_invent_units_without_cited_surface(self) -> None:
        self.assertEqual(extract_requirement_units("Improve operational efficiency for the team."), [])

    def test_ingest_materializes_requirement_units_and_stable_trace_nodes(self) -> None:
        source = self.temp / "requirement.md"
        source.write_text(
            "We need a dashboard with metric cards. Login must support roles and permissions.",
            encoding="utf-8",
        )

        first = ingest("RUDEMO", source)
        second = ingest("RUDEMO", source)

        self.assertEqual(first["requirement_unit_ids"], second["requirement_unit_ids"])
        units_md = self.temp / "workspaces" / "RUDEMO" / "01_discovery" / "requirement_units.md"
        self.assertTrue(units_md.exists())
        text = units_md.read_text(encoding="utf-8")
        self.assertIn("Requirement Units are discovery-time analysis units", text)
        self.assertIn("`RU-001`", text)
        self.assertIn("`dashboard`", text)
        self.assertIn("do not replace Spec Units", text)

        graph = json.loads((self.temp / "workspaces" / "RUDEMO" / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8"))
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(nodes["RU-001"]["type"], "requirement_unit")
        self.assertIn({"from": "RAW-001", "to": "RU-001", "relation": "decomposes_into"}, graph["edges"])
        self.assertIn({"from": "RU-001", "to": "REQ-001", "relation": "analyzes"}, graph["edges"])


if __name__ == "__main__":
    unittest.main()
