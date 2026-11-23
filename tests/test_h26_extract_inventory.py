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

    def test_indented_lines_continue_the_item(self):
        text = (
            "## Reglas de negocio\n"
            "- RN-01: el CUIT del proveedor debe ser único.\n"
            "  - un CUIT duplicado se rechaza.\n"
            "  - el mensaje nombra al proveedor existente.\n"
            "\n"
            "    Aplica también a las altas importadas.\n"
            "- RN-02: un alta rechazada conserva su motivo.\n"
        )
        elements = parse_request_elements(text, "F-01", "p.md")
        self.assertEqual([e["id"] for e in elements], ["RN-01", "RN-02"])
        self.assertEqual(elements[0]["spans"], [[2, 6]])
        self.assertIn("altas importadas", elements[0]["excerpt"])

    def test_paragraph_led_by_an_id_is_an_element(self):
        text = (
            "## Reglas de negocio\n"
            "RN-01: el CUIT del proveedor debe ser único.\n"
            "Un CUIT duplicado se rechaza.\n"
            "\n"
            "**RN-03.** Un alta rechazada conserva su motivo.\n"
            "\n"
            "Texto suelto de la sección.\n"
        )
        elements = parse_request_elements(text, "F-01", "p.md")
        by_id = {e["id"]: e for e in elements}
        self.assertEqual(sorted(by_id), ["RN-01", "RN-03", "SEC-reglas-de-negocio"])
        self.assertEqual(by_id["RN-01"]["spans"], [[2, 3]])
        self.assertEqual(by_id["RN-03"]["kind"], "rule")
        self.assertEqual(by_id["SEC-reglas-de-negocio"]["spans"], [[7, 7]])

    def test_several_h1_are_sections(self):
        text = (
            "# Reglas de negocio\n"
            "- El CUIT del proveedor debe ser único.\n"
            "- Un alta rechazada conserva su motivo.\n"
            "# Criterios de aceptación\n"
            "- Dado un CUIT registrado, cuando se envía el alta, entonces se rechaza.\n"
        )
        elements = parse_request_elements(text, "F-01", "p.md")
        self.assertEqual([e["id"] for e in elements], ["REGLAS-1", "REGLAS-2", "CRITERIOS-1"])
        self.assertEqual(elements[0]["section"], "Reglas de negocio")
        # one H1 is still the title, neither a section nor text
        single = parse_request_elements("# Pedido\n## Reglas\n- uno\n", "F-01", "p.md")
        self.assertEqual([e["id"] for e in single], ["REGLAS-1"])

    def test_criteria_inside_a_story_heading(self):
        text = (
            "### HU-01 Enviar un alta a aprobación\n"
            "Como analista quiero enviar un alta a aprobación.\n"
            "- CA-01: Dado un alta completa, cuando la envío, entonces queda pendiente.\n"
            "- CA-02: Dado un alta incompleta, cuando la envío, entonces se rechaza.\n"
            "- Nota sin id que sigue en la historia.\n"
            "- HU-09 referencia del mismo tipo, no es aparte.\n"
        )
        elements = parse_request_elements(text, "F-01", "p.md")
        by_id = {e["id"]: e for e in elements}
        self.assertEqual(sorted(by_id), ["CA-01", "CA-02", "HU-01"])
        self.assertEqual(by_id["CA-01"]["kind"], "criterion")
        self.assertEqual(by_id["CA-02"]["spans"], [[4, 4]])
        self.assertEqual(by_id["HU-01"]["spans"], [[1, 2], [5, 6]])
        self.assertNotIn("Dado un alta", by_id["HU-01"]["excerpt"])
        # without inner items of another kind the heading element is one span, as before
        plain = parse_request_elements("### HU-03 Consultar\nComo auditor quiero consultar.\n\n", "F-01", "p.md")
        self.assertEqual(plain[0]["spans"], [[1, 2]])

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
