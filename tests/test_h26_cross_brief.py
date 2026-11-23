"""IMP-404 (H26 inc 4) task 6: the cross-reads in the change brief."""
from __future__ import annotations

import json
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.compilers.change_brief import (  # noqa: E402
    collect_change_brief_inputs,
    compile_change_brief,
    render_change_brief,
)
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.crosses.state import crosses_fingerprint  # noqa: E402
from sentinel.crosses.surfaces import accept_new_surface, new_surface_candidates  # noqa: E402
from sentinel.readiness_verdict import _brief_stale  # noqa: E402
from sentinel.changes import get_change  # noqa: E402
from sentinel.status import change_sources  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CROSSES = FIXTURES / "change_crosses"
SAD = FIXTURES / "change_baseline" / "sad-compras.md"
PID = "CRXB"
CID = "CHG-001"


def sections(text: str) -> dict[int, str]:
    parts = re.split(r"^## (\d)\. ", text, flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


class CrossBrief(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(CROSSES / "pedido_contradiccion.md", root / "pedido.md")
        shutil.copy(CROSSES / "harvest_compras.md", root / "harvest_compras.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(SAD), "--role", "linea_de_base", "--change", CID])
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        design = json.loads(run_ok(["sources", PID, "--load", str(CROSSES / "prototipo-aprobaciones.html"),
                                    "--role", "diseno_nuevo", "--change", CID]))["source_id"]
        found = change_sources(PID, CID)["by_role"]
        ids = {"pedido": found["pedido"][0], "diseno": design}
        for kind, name in (("diseno", "cruce_diseno.md"), ("contradicciones", "cruce_contradicciones.md")):
            text = (CROSSES / name).read_text(encoding="utf-8").replace("F-PED", ids["pedido"]).replace("F-DIS", ids["diseno"])
            path = root / f"sub-{name}"
            path.write_text(text, encoding="utf-8")
            record_cross(PID, CID, kind, path)

    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def brief(self) -> str:
        forget_read_snapshots()
        return render_change_brief(collect_change_brief_inputs(PID, CID))[0]

    def test_crosses_line_in_section_1(self):
        s1 = sections(self.brief())[1]
        self.assertIn(
            "Cruces: línea de base: hecho (HECHO 1, NO ENCONTRADO 2); diseño nuevo: hecho (RESPALDADO 2, "
            "SIN RESPALDO EN DISEÑO 1, SOLO EN DISEÑO 1, DIVERGENCIA 1); contradicciones internas: hecho "
            "(CONTRADICCIÓN 1)", s1)

    def test_contradiction_goes_to_section_7(self):
        s = sections(self.brief())
        self.assertRegex(s[7], r"GAP-CON-")
        design = re.search(r"### Diseño\n(.*?)(?=\n### |\Z)", s[5], re.S).group(1)
        self.assertIn("GAP-DIS-", design)
        self.assertIn("GAP-SRD-", design)
        self.assertNotIn("GAP-CON-", s[5])

    def test_accepted_surface_in_section_3(self):
        found = new_surface_candidates(PID, CID)
        accept_new_surface(PID, CID, found[0]["id"], "pantalla", "Historial de aprobaciones")
        forget_read_snapshots()
        self.assertIn("pantalla — Historial de aprobaciones (harvest F-", sections(self.brief())[3])

    def test_brief_goes_stale_with_crosses(self):
        compile_change_brief(PID, CID)
        base = workspace_path(PID)
        forget_read_snapshots()
        self.assertFalse(_brief_stale(base, CID, get_change(PID, CID)))
        found = new_surface_candidates(PID, CID)
        accept_new_surface(PID, CID, found[0]["id"], "pantalla", "Historial de aprobaciones")
        forget_read_snapshots()
        self.assertTrue(_brief_stale(base, CID, get_change(PID, CID)))


class NoCrosses(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "CRXN0"])
        run_ok(["ingest", "CRXN0", "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", "CRXN0", "--source", "scope.md", "--change", CID])

    def test_no_crosses_no_change(self):
        forget_read_snapshots()
        text, report = render_change_brief(collect_change_brief_inputs("CRXN0", CID))
        self.assertNotIn("Cruces:", text)
        self.assertNotIn("Cross-reads:", text)
        self.assertEqual(report["crosses_fingerprint"], crosses_fingerprint("CRXN0", CID))
        self.assertEqual(report["crosses_fingerprint"], "")
        compile_change_brief("CRXN0", CID)
        forget_read_snapshots()
        self.assertFalse(_brief_stale(workspace_path("CRXN0"), CID, get_change("CRXN0", CID)))


if __name__ == "__main__":
    unittest.main()
