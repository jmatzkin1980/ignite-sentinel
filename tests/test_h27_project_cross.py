"""IMP-420 (H27 inc 6b) task 4: the project's cross-reads, with gaps by exact id in the project's gaps.md."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, ProjectExtractionCase, run_ok  # noqa: E402

from sentinel.changes import change_gaps_path  # noqa: E402
from sentinel.core.io import forget_read_snapshots, read_json  # noqa: E402
from sentinel.crosses import cross_path, crosses_dir  # noqa: E402
from sentinel.crosses.claims import cross_sources  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.crosses.state import cross_status  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.prior_decisions import load_priors  # noqa: E402
from sentinel.core.state import read_state as load_state  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = ProjectExtractionCase.PID
PROJECT = ProjectExtractionCase.FIXTURES
CROSSES = PROJECT.parent / "change_crosses"


class ProjectCross(ProjectExtractionCase):
    @classmethod
    def build_workspace(cls) -> None:
        super().build_workspace()
        run_ok(["sources", cls.PID, "--load", str(cls.FIXTURES / "prototipo-alta-proveedor.html"), "--role", "diseno_nuevo"])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def ids(self) -> dict[str, str]:
        found = cross_sources(PID, None)
        return {"pedido": sorted(found["pedido"])[0], "diseno": sorted(found["diseno"])[0]}

    def claims(self, name: str, text: str | None = None) -> Path:
        ids = self.ids()
        body = text if text is not None else (PROJECT / name).read_text(encoding="utf-8")
        body = body.replace("F-PED", ids["pedido"]).replace("F-DIS", ids["diseno"])
        path = Path.cwd() / f"sub-{len(list(Path.cwd().glob('sub-*')))}-{name}"
        path.write_text(body, encoding="utf-8")
        return path

    def project_gaps(self) -> dict[str, dict]:
        path = workspace_path(PID) / "01_discovery" / "gaps.md"
        return {g["id"]: g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g.get("id") != "NONE"}

    def add_change(self) -> None:
        shutil.copy(CROSSES / "pedido_contradiccion.md", Path.cwd() / "pedido-cambio.md")
        run_ok(["ingest", PID, "--source", "pedido-cambio.md", "--change"])
        forget_read_snapshots()

    def test_project_cross_recorded(self):
        record_cross(PID, None, "contradicciones", self.claims("cruce_contradicciones.md"))
        base = workspace_path(PID)
        path = base / "01_discovery" / "crosses" / "contradicciones.json"
        self.assertTrue(path.is_file())
        self.assertEqual(cross_path(base, None, "contradicciones"), path)
        record = read_json(path, {})
        self.assertEqual(record["basis"]["pedido"], [self.ids()["pedido"]])
        self.assertTrue((base / "01_discovery" / "crosses.md").is_file())
        self.assertFalse((crosses_dir(base, None) / "crosses.md").exists())
        kinds = cross_status(PID, None)["kinds"]
        self.assertEqual(kinds["contradicciones"]["state"], "done")
        self.assertEqual(kinds["linea_de_base"]["state"], "waived")

    def test_project_cross_gaps_exact_ids_in_project_gaps(self):
        before = set(self.project_gaps())
        result = record_cross(PID, None, "contradicciones", self.claims("cruce_contradicciones_tema.md"))
        opened = result["gaps_opened"]
        self.assertEqual(len(opened), 2)
        self.assertTrue(all(g.startswith("GAP-CON-") for g in opened))
        gaps = self.project_gaps()
        self.assertTrue(set(opened) <= set(gaps))
        self.assertTrue(before <= set(gaps))  # the rows of the intake stay
        self.assertEqual(load_state(PID)["gap_counts"]["total"], len(gaps))
        forget_read_snapshots()
        again = record_cross(PID, None, "contradicciones", self.claims("cruce_contradicciones_tema.md"))
        self.assertEqual(again["gaps_opened"], [])
        self.assertEqual(len(self.project_gaps()), len(gaps))

    def test_project_cross_leaves_change_gaps_untouched(self):
        self.add_change()
        path = change_gaps_path(workspace_path(PID), "CHG-001")
        before = path.read_bytes()
        changes_before = {k: dict(v) for k, v in load_state(PID)["changes"].items()}
        record_cross(PID, None, "contradicciones", self.claims("cruce_contradicciones_tema.md"))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(load_state(PID)["changes"], changes_before)

    def test_decided_contradiction_not_asked_twice(self):
        result = record_cross(PID, None, "diseno", self.claims("cruce_diseno.md"))
        gap = next(g for g in result["gaps_opened"] if g.startswith("GAP-DIS-"))
        prior = load_priors(workspace_path(PID), None)[gap]
        self.assertEqual(prior["match"], "design_request")
        self.assertIn("Ya registrado en el pedido como pedido a Diseño: PD-01.", self.project_gaps()[gap]["description"])
        self.assertEqual(result["design_requests"], [gap])

    def test_screen_without_endpoint_is_a_claim(self):
        result = record_cross(PID, None, "diseno", self.claims("cruce_diseno.md"))
        self.assertTrue(any(g.startswith("GAP-SED-") for g in result["gaps_opened"]))
        self.assertTrue(any(g.startswith("GAP-SED-") for g in self.project_gaps()))

    def test_quote_not_in_request_refused(self):
        text = (PROJECT / "cruce_contradicciones.md").read_text(encoding="utf-8").replace(
            "mayor a 5.000.000 requiere doble aprobación.", "mayor a 7.000.000 requiere triple firma.")
        with self.assertRaises(InputError):
            record_cross(PID, None, "contradicciones", self.claims("cruce_malo.md", text))
        self.assertFalse((workspace_path(PID) / "01_discovery" / "crosses").exists())

    def test_project_cross_ignores_change_rows(self):
        self.add_change()
        run_ok(["sources", PID, "--load", str(CROSSES / "prototipo-aprobaciones.html"),
                "--role", "diseno_nuevo", "--change", "CHG-001"])
        forget_read_snapshots()
        project_design = set(cross_sources(PID, None)["diseno"])
        change_design = set(cross_sources(PID, "CHG-001")["diseno"])
        self.assertEqual(len(project_design), 1)
        self.assertTrue(project_design < change_design)  # the change still reads every current prototype
        self.assertEqual(len(change_design), 2)

    def test_project_baseline_needs_harvest(self):
        run_ok(["sources", PID, "--load", str(PROJECT.parent / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base"])
        forget_read_snapshots()
        self.assertEqual(cross_status(PID, None)["kinds"]["linea_de_base"]["state"], "missing")


if __name__ == "__main__":
    unittest.main()
