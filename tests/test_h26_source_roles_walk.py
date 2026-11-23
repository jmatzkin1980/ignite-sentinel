"""IMP-400 (H26 inc 2): end-to-end walk of the sources by role inside one change."""
from __future__ import annotations

import json
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.changes import change_gaps_path, list_changes  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402

VERSIONS = Path(__file__).resolve().parent / "fixtures" / "change_versions"
PROJECT = "WLK"
CID = "CHG-001"
QUOTE = "El servicio valida los datos fiscales (CUIT) y bancarios (CBU) antes de crear el proveedor"


def tech_answer(evidence: str) -> str:
    return "\n".join([
        "### GAP-TECH-NFR",
        "- Respuesta: La validación vigente del alta aplica sin cambios a este cambio.",
        "- Owner / fuente: Arquitectura",
        f"- Evidencia o referencia: {evidence}",
        "- Estado de decisión: confirmado",
        "- Motivo de cierre: by_baseline",
        "",
    ])


class SourceRolesWalk(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(VERSIONS / "pedido_con_citas.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PROJECT])

    def rows(self) -> dict[str, dict]:
        text = change_gaps_path(workspace_path(PROJECT), CID).read_text(encoding="utf-8")
        return {r["id"]: r for r in parse_gap_rows(text)}

    def resolve(self, name: str, text: str) -> list[str]:
        Path(name).write_text(text, encoding="utf-8")
        out = json.loads(run_ok(["resolve-gaps", PROJECT, "--source", name, "--change", CID]))
        return out["closure_findings"]

    def next_key(self) -> str:
        return json.loads(run_ok(["next", PROJECT, "--change", CID]))["key"]

    def blocking_open(self) -> int:
        return list_changes(PROJECT)[CID]["gap_counts"]["blocking_open"]

    def test_walk(self):
        # 1. The request, with its citations, opens the change.
        out = json.loads(run_ok(["ingest", PROJECT, "--source", "pedido.md", "--change"]))
        self.assertEqual(out["change_id"], CID)

        # 2. The border closes the scope round.
        run_ok(["resolve-gaps", PROJECT, "--source", "scope.md", "--change", CID])
        self.assertEqual(self.rows()["GAP-SCOPE"]["status"], "CLOSED")

        # 3. /next asks for the baseline before the lenses.
        self.assertEqual(self.next_key(), "baseline")
        blocking_before = self.blocking_open()

        # 4. The loaded baseline is another version than the one the request cites: GAP-VER opens.
        loaded = json.loads(run_ok(["sources", PROJECT, "--load", str(VERSIONS / "sad-compras-v2.md"),
                                    "--role", "linea_de_base", "--change", CID]))
        self.assertEqual(loaded["role"], "linea_de_base")
        self.assertEqual(len(loaded["version_gaps"]), 1)
        ver_id = loaded["version_gaps"][0]
        self.assertTrue(re.fullmatch(r"GAP-VER-[0-9A-F]{6}", ver_id))
        self.assertEqual(self.rows()[ver_id]["status"], "OPEN")
        self.assertEqual(self.blocking_open(), blocking_before + 1)  # the GAP-VER blocks
        self.assertNotEqual(self.next_key(), "baseline")

        # 5. The synthetic prototype is the design of what is new.
        proto = json.loads(run_ok(["sources", PROJECT, "--load", str(VERSIONS / "prototipo-alta.md"),
                                   "--role", "diseno_nuevo", "--change", CID]))
        self.assertEqual(proto["role"], "diseno_nuevo")
        proto_path = proto["path"].split("workspaces/%s/" % PROJECT)[-1]
        self.assertIn("08_new_design", proto_path)
        base_path = loaded["path"].split("workspaces/%s/" % PROJECT)[-1]
        self.assertIn("06_baseline", base_path)

        # 6. A by_baseline that cites the prototype is rejected: it is not the baseline.
        findings = self.resolve("resp_proto.md", tech_answer(f'`{proto_path}` "Una lista Mis borradores permite retomar un borrador guardado"'))
        row = self.rows()["GAP-TECH-NFR"]
        self.assertEqual(row["status"], "ANSWERED")
        self.assertNotEqual(row.get("closure_reason"), "by_baseline")
        self.assertIn("diseno_nuevo", " ".join(findings))

        # 7. Citing the baseline closes it.
        findings = self.resolve("resp_base.md", tech_answer(f'`{base_path}` "{QUOTE}"'))
        row = self.rows()["GAP-TECH-NFR"]
        self.assertEqual(row["status"], "CLOSED", findings)
        self.assertEqual(row["closure_reason"], "by_baseline")

        # 8. The BA answers the version gap: the loaded version governs.
        self.resolve("resp_ver.md", "\n".join([
            f"### {ver_id}",
            "- Respuesta: (A) rige la cargada: la cita del pedido está desactualizada y el SAD v2 es la línea de base vigente.",
            "- Owner / fuente: Arquitectura",
            "- Estado de decisión: confirmado",
            "",
        ]))
        self.assertEqual(self.rows()[ver_id]["status"], "CLOSED")

        # 9. /status --change shows the sources by role.
        status = json.loads(run_ok(["status", PROJECT, "--change", CID]))
        sources = status["sources"]
        for role in ("pedido", "linea_de_base", "diseno_nuevo"):
            self.assertIn(role, sources["by_role"])
        self.assertTrue(sources["baseline"])
        self.assertIn("manual-compras.md", sources["not_loaded"])
        self.assertFalse(any(w["trigger"] == "no_baseline" for w in status["warnings"]))


if __name__ == "__main__":
    unittest.main()
