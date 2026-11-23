"""IMP-402 (H26 inc 3) task 1: the inventory of a change request, element by element."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.extraction import extraction_dir  # noqa: E402
from sentinel.extraction.inventory import (  # noqa: E402
    build_inventory,
    element_text,
    home_section,
    inventory_state,
    load_inventory,
    match_element_id,
    parse_request_elements,
    section_slug,
)
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
IDS = FIXTURES / "change_extraction" / "pedido_ids.md"
PID = "EXI"

EXPECTED_IDS = (
    ["SEC-objetivo", "SEC-usuarios", "SEC-situacion-actual-y-estado-futuro", "SEC-proceso"]
    + ["HU-01", "HU-02", "HU-03"]
    + [f"RN-0{n}" for n in range(1, 7)]
    + [f"CA-0{n}" for n in range(1, 6)]
    + ["PD-01", "PD-02", "SEC-se-preserva", "SEC-fuera-de-alcance"]
)


def parse(path: Path) -> list[dict]:
    return parse_request_elements(path.read_text(encoding="utf-8"), "F-01", "pedido.md")


class Parsing(unittest.TestCase):
    def test_id_patterns(self):
        for line, expected in (
            ("RN-01: x", "RN-01"),
            ("**RN-03** — x", "RN-03"),
            ("`CA-01` x", "CA-01"),
            ("| RN-04 | x |", "RN-04"),
            ("- Regla 10.2: x", "Regla 10.2"),
            ("3. HU-7 x", "HU-7"),
            ("Decisión 2: x", "Decisión 2"),
            ("Regla 10.2. x", "Regla 10.2"),
        ):
            with self.subTest(line=line):
                found = match_element_id(line)
                self.assertIsNotNone(found)
                self.assertEqual(found[0], expected)
        self.assertEqual(match_element_id("Decisión 2: x")[1], "decision")
        for line in ("US-001 x", "REQ-EARS-001 x", "RNX-1 x", "Reglamento 1 x", "Una RN-01 en el medio"):
            with self.subTest(line=line):
                self.assertIsNone(match_element_id(line))

    def test_section_slug_and_home(self):
        self.assertEqual(section_slug("3. Situación actual y estado futuro"), "situacion-actual-y-estado-futuro")
        self.assertEqual(section_slug("   "), "seccion")
        self.assertEqual(home_section("section", "Fuera de alcance"), 3)
        self.assertEqual(home_section("story", "x"), 4)
        self.assertEqual(home_section("rule", "x"), 7)
        self.assertIsNone(home_section("section", "Glosario"))

    def test_ids_fixture_inventory(self):
        elements = parse(IDS)
        self.assertEqual(sorted(e["id"] for e in elements), sorted(EXPECTED_IDS))
        self.assertEqual(len(elements), 22)
        counts = {}
        for element in elements:
            counts[element["kind"]] = counts.get(element["kind"], 0) + 1
        self.assertEqual(counts, {"section": 6, "story": 3, "rule": 6, "criterion": 5, "decision": 2})
        by_id = {e["id"]: e for e in elements}
        self.assertEqual(by_id["RN-01"]["line"], 30)
        self.assertEqual(by_id["RN-06"]["line"], 35)
        self.assertEqual(by_id["SEC-usuarios"]["spans"], [[7, 9]])
        self.assertEqual(by_id["HU-03"]["spans"], [[24, 25]])
        self.assertEqual(by_id["RN-01"]["home"], 7)
        self.assertEqual(by_id["SEC-fuera-de-alcance"]["home"], 3)
        self.assertEqual(len(by_id["RN-01"]["sha"]), 16)
        self.assertFalse([e for e in elements if e["id"] in ("ID", "---")])

    def test_mature_fixture_inventory(self):
        elements = parse(FIXTURES / "change_mature" / "pedido_maduro.md")
        self.assertEqual(
            sorted(e["id"] for e in elements),
            sorted(
                [f"Regla {n}" for n in range(1, 5)] + [f"CRITERIOS-{n}" for n in range(1, 5)]
                + ["SEC-objetivo", "SEC-usuarios", "SEC-situacion-actual-y-estado-futuro", "SEC-proceso", "SEC-se-preserva"]
            ),
        )
        self.assertEqual(len(elements), 13)
        self.assertEqual({e["kind"] for e in elements if e["id"].startswith("Regla")}, {"rule"})
        self.assertEqual({e["kind"] for e in elements if e["id"].startswith("CRITERIOS")}, {"criterion"})

    def test_borrador_is_one_section(self):
        elements = parse(FIXTURES / "change_borrador.md")
        self.assertEqual([e["id"] for e in elements], ["SEC-intro"])
        self.assertEqual(elements[0]["spans"], [[3, 7]])

    def test_duplicate_ids(self):
        text = "## Reglas\n- RN-01: uno\n- RN-01: dos\n"
        self.assertEqual([e["id"] for e in parse_request_elements(text, "F-01", "p.md")], ["RN-01", "RN-01#2"])


class Build(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(IDS, Path.cwd() / "pedido.md")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["init", "PRJ"])
        run_ok(["ingest", "PRJ", "--source", "pedido.md"])

    def test_build_inventory_writes_files_and_is_idempotent(self):
        result = build_inventory(PID, "CHG-001")
        base = workspace_path(PID)
        folder = extraction_dir(base, "CHG-001")
        self.assertTrue((folder / "inventory.json").is_file())
        sheet = (folder / "proposals_template.md").read_text(encoding="utf-8")
        self.assertIn("### RN-04", sheet)
        self.assertIn("- Tratamiento:", sheet)
        self.assertEqual((result["version"], result["total"], result["action"]), (1, 22, "inventory"))
        self.assertTrue(result["changed"])
        self.assertEqual(result["unreadable"], [])
        self.assertEqual(result["stale_proposals"], [])
        again = build_inventory(PID, "CHG-001")
        self.assertEqual(again["version"], 1)
        self.assertFalse(again["changed"])
        self.assertEqual(inventory_state(PID, "CHG-001"), "current")
        inventory = load_inventory(base, "CHG-001")
        rn = next(e for e in inventory["elements"] if e["id"] == "RN-02")
        self.assertIn("5.000.000", element_text(base, rn))

    def test_inventory_goes_stale_when_a_request_is_loaded(self):
        build_inventory(PID, "CHG-001")
        self.assertEqual(inventory_state(PID, "CHG-001"), "current")
        second = Path.cwd() / "pedido-2.md"
        second.write_text("## Reglas\n- RN-01: Otra regla del segundo pedido.\n- Una regla sin id.\n", encoding="utf-8")
        run_ok(["sources", PID, "--load", str(second), "--role", "pedido", "--change", "CHG-001"])
        self.assertEqual(inventory_state(PID, "CHG-001"), "stale")
        result = build_inventory(PID, "CHG-001")
        ids = {e["id"] for e in load_inventory(workspace_path(PID), "CHG-001")["elements"]}
        self.assertTrue(set(EXPECTED_IDS) <= ids)
        self.assertIn("RN-01@F-02", ids)
        self.assertIn("REGLAS-1", ids)
        self.assertEqual(result["version"], 2)
        self.assertEqual(inventory_state(PID, "CHG-001"), "current")

    def test_missing_state(self):
        self.assertEqual(inventory_state(PID, "CHG-001"), "missing")

    def test_project_ingest_has_no_extraction(self):
        self.assertFalse(list(workspace_path("PRJ").rglob("extraction")))


if __name__ == "__main__":
    unittest.main()
