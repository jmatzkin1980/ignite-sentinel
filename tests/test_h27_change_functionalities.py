"""IMP-416 task 1: the functionalities of a change (FUN-nn by border surface) and the story size of the slicing model."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402

from sentinel.change_requirements import load_change_ears, parse_delta  # noqa: E402
from sentinel.compilers.change_functionalities import (  # noqa: E402
    change_functionalities, functionalities_sha, story_size,
)
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.surfaces import accept_new_surface, new_surface_candidates  # noqa: E402
from sentinel.slicing_model import load_slicing_model  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CROSSES = FIXTURES / "change_crosses"
PID = "FUNC"
CID = "CHG-001"
NEW = "Bandeja de aprobación"
TABLE = "Tabla de proveedores"


def _answer(gap: str, text: str, delta: str, surface: str) -> str:
    return (f"### {gap}\n- Respuesta: {text}\n- Owner / fuente: Jefa de Compras\n- Delta: {delta}\n"
            f"- Superficie: {surface}\n- Estado de decisión: confirmado\n")


ANSWERS = "\n".join([
    _answer("GAP-ACCEPTANCE",
            "Cuando el comprador guarda el alta incompleta, el sistema debe conservar los datos cargados. "
            "Cuando el comprador abre la lista de pendientes, el sistema debe listar sus altas incompletas.",
            "ADDED", NEW),
    _answer("GAP-OBJECTIVE",
            "Cuando el comprador cambia el texto del aviso, el sistema debe mostrar el aviso nuevo.",
            "MODIFIED", TABLE),
    _answer("GAP-TECH-NFR",
            "Cuando el comprador consulta sus altas incompletas, el sistema debe responder en menos de dos segundos.",
            "ADDED", TABLE),
    _answer("GAP-USERS",
            "Cuando el comprador sigue enviando el alta completa, el sistema debe continuar validando los datos.",
            "UNCHANGED", TABLE),
])


class ChangeFunctionalities(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        shutil.copy(CROSSES / "harvest_compras.md", root / "harvest_compras.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        (root / "answers.md").write_text(ANSWERS, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        accept_new_surface(PID, CID, new_surface_candidates(PID, CID)[0]["id"], "pantalla", NEW)
        run_ok(["resolve-gaps", PID, "--source", "answers.md", "--change", CID])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.rows = load_change_ears(PID, CID)

    def funs(self, rows: list[dict] | None = None) -> list[dict]:
        return change_functionalities(PID, CID, rows)

    def by_name(self, name: str) -> dict:
        return next(f for f in self.funs() if f["name"] == name)

    def test_groups_rows_by_primary_surface(self):
        funs = self.funs()
        table = self.by_name(TABLE)
        self.assertEqual((table["type"], table["zone"], table["key"]), ("dato", "adyacente", "dato:tabla de proveedores"))
        grouped = [r for f in funs for r in f["rows"]]
        self.assertEqual(len(grouped), len(set(grouped)))
        units = {r["id"] for r in self.rows if parse_delta(r["delta"]) in ("ADDED", "MODIFIED", "REMOVED")}
        self.assertEqual(set(grouped), units)
        self.assertGreaterEqual(len(table["rows"]), 2)

    def test_new_surfaces_first_and_positional_ids(self):
        funs = self.funs()
        self.assertEqual(funs[0]["name"], NEW)
        self.assertEqual((funs[0]["id"], funs[0]["zone"], funs[0]["origin"]), ("FUN-01", "nuevo", "cross"))
        self.assertEqual(self.by_name(TABLE)["id"], "FUN-02")
        self.assertEqual(funs, self.funs())

    def test_unchanged_rows_go_to_no_regression(self):
        unchanged = [r["id"] for r in self.rows if r["delta"] == "UNCHANGED" and "continuar validando" in r["statement"]]
        self.assertEqual(len(unchanged), 1)
        self.assertIn(unchanged[0], self.by_name(TABLE)["preserved"])
        self.assertFalse([r for f in self.funs() for r in f["rows"] if r in unchanged])

    def test_row_without_surface_groups_by_place(self):
        extra = {"id": "REQ-EARS-900", "pattern": "event", "delta": "ADDED", "statement": "Cuando A, el sistema debe B.",
                 "source": "`GAP-ACCEPTANCE` / `CHG-001`", "affects": [], "surfaces": []}
        funs = self.funs(self.rows + [extra])
        last = funs[-1]
        self.assertEqual((last["key"], last["place"], last["type"], last["name"]), ("lugar:2.2", "2.2", "", ""))
        self.assertEqual(last["rows"], ["REQ-EARS-900"])
        self.assertEqual(last["gaps"], ["GAP-ACCEPTANCE"])

    def test_depends_on_new_surface(self):
        extra = {"id": "REQ-EARS-901", "pattern": "event", "delta": "ADDED", "statement": "Cuando A, el sistema debe B.",
                 "source": "`GAP-ACCEPTANCE` / `CHG-001`", "affects": [], "surfaces": [TABLE, NEW]}
        funs = self.funs(self.rows + [extra])
        table = next(f for f in funs if f["name"] == TABLE)
        self.assertIn("REQ-EARS-901", table["rows"])
        self.assertEqual(table["depends_on"], ["FUN-01"])
        self.assertEqual(next(f for f in funs if f["name"] == NEW)["depends_on"], [])

    def test_sha_follows_grouping_and_units(self):
        funs = self.funs()
        unit_of = {rid: f"SPEC-U-{n:03d}" for n, rid in enumerate((r for f in funs for r in f["rows"]), 1)}
        first = functionalities_sha(funs, unit_of)
        self.assertRegex(first, r"^[0-9a-f]{16}$")
        self.assertEqual(first, functionalities_sha(funs, dict(unit_of)))
        swapped = dict(unit_of)
        key = funs[0]["rows"][0]
        swapped[key] = "SPEC-U-999"
        self.assertNotEqual(first, functionalities_sha(funs, swapped))


class StorySize(unittest.TestCase):
    def test_story_size_from_model(self):
        self.assertEqual(story_size(), 5)
        data = json.loads(json.dumps(load_slicing_model()))
        del data["story_size"]
        self.assertEqual(load_slicing_model(override=data)["story_size"], {"max_units": 5})
        data["story_size"] = {"max_units": 0}
        with self.assertRaises(ValueError) as caught:
            load_slicing_model(override=data)
        self.assertIn("story_size.max_units", str(caught.exception))
        data["story_size"] = {"max_units": 3}
        self.assertEqual(story_size(load_slicing_model(override=data)), 3)


if __name__ == "__main__":
    unittest.main()
