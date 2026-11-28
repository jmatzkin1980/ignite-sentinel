"""IMP-404 (H26 inc 4) task 4: the harvest is the baseline cross; its NOT FOUND entries propose new surfaces."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, place_harvest_docs, run_ok  # noqa: E402

from sentinel.changes import confirm_border, list_changes, parse_border  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses import crosses_dir  # noqa: E402
from sentinel.crosses.state import cross_status  # noqa: E402
from sentinel.crosses.surfaces import accept_new_surface, decline_new_surface, new_surface_candidates  # noqa: E402
from sentinel.errors import GateRefusal, InputError  # noqa: E402
from sentinel.workspace import read_state, workspace_path  # noqa: E402

CROSSES = Path(__file__).resolve().parent / "fixtures" / "change_crosses"
PID = "CRZS"
CID = "CHG-001"


class SurfaceCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(CROSSES / "pedido_contradiccion.md", root / "pedido.md")
        shutil.copy(CROSSES / "harvest_compras.md", root / "harvest_compras.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        place_harvest_docs(PID, (root / "harvest_compras.md").read_text(encoding="utf-8"))  # IMP-435 (B-37)
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def candidates(self) -> dict[str, dict]:
        return {c["text"]: c for c in new_surface_candidates(PID, CID)}

    def historial(self) -> str:
        return self.candidates()["No existe un historial de aprobaciones por alta de proveedor."]["id"]

    def bandeja(self) -> str:
        return self.candidates()["No hay una bandeja de aprobaciones de altas para la jefatura."]["id"]

    def report(self) -> str:
        return (crosses_dir(workspace_path(PID), CID) / "crosses.md").read_text(encoding="utf-8")


class Harvest(SurfaceCase):
    def test_change_harvest_is_the_baseline_cross(self):
        harvests = list_changes(PID)[CID]["harvests"]
        self.assertEqual(len(harvests), 1)
        self.assertTrue(harvests[0].startswith("F-"))
        info = cross_status(PID, CID)["kinds"]["linea_de_base"]
        self.assertEqual(info["state"], "done")
        self.assertEqual(info["counts"], {"fact": 1, "not_found": 2})

    def test_project_harvest_adds_no_harvests(self):
        run_ok(["init", "CRZP"])
        place_harvest_docs("CRZP", Path("harvest_compras.md").read_text(encoding="utf-8"))  # IMP-435 (B-37)
        run_ok(["harvest", "CRZP", "--source", "harvest_compras.md"])
        self.assertEqual(list_changes("CRZP"), {})
        self.assertNotIn("harvests", read_state("CRZP"))

    def test_candidates(self):
        found = new_surface_candidates(PID, CID)
        self.assertEqual(len(found), 2)
        for item in found:
            self.assertRegex(item["id"], r"^NEW-[0-9A-F]{6}$")
            self.assertIsNone(item["decision"])
        ids = [c["id"] for c in found]
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        self.assertEqual([c["id"] for c in new_surface_candidates(PID, CID)], ids)
        self.assertEqual(len(list_changes(PID)[CID]["harvests"]), 1)


class Accepting(SurfaceCase):
    def test_accept_adds_a_new_surface(self):
        cid = self.historial()
        result = accept_new_surface(PID, CID, cid, "pantalla", "Historial de aprobaciones")
        self.assertEqual(result["action"], "accept_new")
        border = list_changes(PID)[CID]["border"]
        last = border[-1]
        self.assertEqual((last["zone"], last["origin"], last["name"]), ("nuevo", "cross", "Historial de aprobaciones"))
        self.assertIn(list_changes(PID)[CID]["harvests"][0], last["cite"])
        self.assertIn(cid, last["cite"])
        self.assertIn("aceptada como pantalla «Historial de aprobaciones»", self.report())
        self.assertIn("## Candidatas a superficie nueva (del harvest)", self.report())

    def test_accept_rules(self):
        cid = self.historial()
        with self.assertRaises(InputError):
            accept_new_surface(PID, CID, cid, "pantalla", "bandeja de aprobaciones")
        with self.assertRaises(InputError):
            accept_new_surface(PID, CID, cid, "pagina", "Historial de aprobaciones")
        with self.assertRaises(InputError):
            accept_new_surface(PID, CID, cid, "pantalla", "Historial; de aprobaciones")
        with self.assertRaises(InputError):
            accept_new_surface(PID, CID, "NEW-000000", "pantalla", "Historial de aprobaciones")
        accept_new_surface(PID, CID, cid, "integración", "Historial de aprobaciones")
        self.assertEqual(list_changes(PID)[CID]["new_surfaces"][cid]["type"], "integracion")
        with self.assertRaises(InputError):
            accept_new_surface(PID, CID, cid, "pantalla", "Otro historial")

    def test_decline(self):
        cid = self.historial()
        with self.assertRaises(InputError):
            decline_new_surface(PID, CID, cid, "  ")
        result = decline_new_surface(PID, CID, cid, "ya existe en la bandeja")
        self.assertEqual(result["action"], "decline_new")
        self.assertEqual(list_changes(PID)[CID]["new_surfaces"][cid]["decision"], "declined")
        self.assertIn("descartada: ya existe en la bandeja", self.report())

    def test_decline_an_accepted_surface(self):
        cid = self.historial()
        accept_new_surface(PID, CID, cid, "pantalla", "Historial de aprobaciones")
        rows = [{"id": "REQ-EARS-001", "delta": "ADDED", "surfaces": ["Historial de aprobaciones"]}]
        with patch("sentinel.crosses.surfaces.load_change_ears", return_value=rows):
            with self.assertRaises(InputError) as caught:
                decline_new_surface(PID, CID, cid, "no va")
        self.assertIn("REQ-EARS-001", str(caught.exception))
        self.assertTrue(any(i.get("candidate") == cid for i in list_changes(PID)[CID]["border"]))
        decline_new_surface(PID, CID, cid, "no va")
        self.assertFalse(any(i.get("candidate") == cid for i in list_changes(PID)[CID]["border"]))

    def test_scope_reconfirmed_keeps_cross_surfaces(self):
        accept_new_surface(PID, CID, self.historial(), "pantalla", "Historial de aprobaciones")
        confirm_border(PID, CID, parse_border(IDS_SCOPE_ANSWER, "x"))
        border = list_changes(PID)[CID]["border"]
        self.assertEqual(len(border), 7)
        self.assertEqual(border[-1]["name"], "Historial de aprobaciones")
        self.assertEqual(border[-1]["origin"], "cross")

    def test_accept_refused_in_scope_round(self):
        shutil.copy(CROSSES / "pedido_contradiccion.md", Path.cwd() / "otro.md")
        run_ok(["init", "CRZQ"])
        run_ok(["ingest", "CRZQ", "--source", "otro.md", "--change"])
        place_harvest_docs("CRZQ", Path("harvest_compras.md").read_text(encoding="utf-8"))  # IMP-435 (B-37)
        run_ok(["harvest", "CRZQ", "--source", "harvest_compras.md", "--change", CID])
        cid = new_surface_candidates("CRZQ", CID)[0]["id"]
        with self.assertRaises(GateRefusal):
            accept_new_surface("CRZQ", CID, cid, "pantalla", "Historial de aprobaciones")


if __name__ == "__main__":
    unittest.main()
