"""IMP-400 (H26 inc 2): by_baseline closes only from a source registered as the baseline."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.changes import change_gaps_path  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.sources import load_source_manifest, open_source_row  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_baseline_closure import QUOTE, SAD_TEXT, SCOPE_ANSWER, answer  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HARVEST = """# Harvest

## B0 Inventory
- repo: compras-api — services/compras

## B6 Pantallas
- [HECHO compras-api:services/compras/alta.py] El servicio de compras responde en menos de dos segundos al percentil 95 en horario pico.
"""
PROJECT = "RBL"


def cite(path: str) -> str:
    return f'`{path}` "{QUOTE}"'


class BaselineRole(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PROJECT])
        run_ok(["ingest", PROJECT, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PROJECT, "--source", "scope.md", "--change", "CHG-001"])

    def load(self, name: str, role: str, text: str = SAD_TEXT) -> dict:
        folder = Path("in")
        folder.mkdir(exist_ok=True)
        (folder / name).write_text(text, encoding="utf-8")
        return json.loads(run_ok(["sources", PROJECT, "--load", str(folder / name), "--role", role, "--change", "CHG-001"]))

    def resolve(self, evidence: str) -> tuple[dict, list[str]]:
        Path("resp.md").write_text(answer(evidence), encoding="utf-8")
        out = json.loads(run_ok(["resolve-gaps", PROJECT, "--source", "resp.md", "--change", "CHG-001"]))
        rows = parse_gap_rows(change_gaps_path(workspace_path(PROJECT), "CHG-001").read_text(encoding="utf-8"))
        return next(r for r in rows if r["id"] == "GAP-TECH-NFR"), out["closure_findings"]

    def assertRejected(self, evidence: str, *needles: str) -> None:
        row, findings = self.resolve(evidence)
        self.assertEqual(row["status"], "ANSWERED")
        self.assertNotEqual(row.get("closure_reason"), "by_baseline")
        text = " ".join(findings)
        for needle in needles:
            self.assertIn(needle, text, findings)

    def test_closes_from_loaded_baseline(self):
        self.load("sad-compras.md", "linea_de_base")
        row, findings = self.resolve(cite("00_raw/06_baseline/sad-compras.md"))
        self.assertEqual(row["status"], "CLOSED")
        self.assertEqual(row["closure_reason"], "by_baseline")
        self.assertEqual(findings, [])

    def test_rejects_unregistered_hand_copy(self):
        path = workspace_path(PROJECT) / "00_raw" / "02_technology_context" / "sad-compras.md"
        path.write_text(SAD_TEXT, encoding="utf-8")
        self.assertRejected(cite("00_raw/02_technology_context/sad-compras.md"), "--load", "--role linea_de_base")

    def test_rejects_harvest_copy(self):
        Path("h.md").write_text(HARVEST, encoding="utf-8")
        run_ok(["harvest", PROJECT, "--source", "h.md", "--change", "CHG-001"])
        folder = workspace_path(PROJECT) / "00_raw" / "02_technology_context" / "harvest"
        copies = sorted(p for p in folder.iterdir() if p.is_file())
        self.assertTrue(copies)
        rel = f"00_raw/02_technology_context/harvest/{copies[0].name}"
        self.assertRejected(f'`{rel}` "responde en menos de dos segundos al percentil 95"', "lectura de Sentinel")
        row, findings = self.resolve(f'`{rel}` "responde en menos de dos segundos al percentil 95"')
        self.assertNotIn("--load", " ".join(findings))

    def test_rejects_plan_previo(self):
        self.load("plan-previo.md", "plan_previo")
        self.assertRejected(cite("00_raw/07_prior_plan/plan-previo.md"), "plan_previo")

    def test_rejects_diseno_nuevo(self):
        self.load("diseno.md", "diseno_nuevo")
        self.assertRejected(cite("00_raw/08_new_design/diseno.md"), "diseno_nuevo")

    def test_rejects_superseded_baseline(self):
        old = self.load("sad-vieja.md", "linea_de_base")
        new = self.load("sad-nueva.md", "linea_de_base", SAD_TEXT + "Version nueva.\n")
        run_ok(["sources", PROJECT, "--id", old["source_id"], "--superseded-by", new["source_id"]])
        self.assertRejected(cite("00_raw/06_baseline/sad-vieja.md"), new["source_id"])

    def test_accepts_registered_inferred_baseline(self):
        folder = workspace_path(PROJECT) / "00_raw" / "02_technology_context"
        (folder / "sad-registrada.md").write_text(SAD_TEXT, encoding="utf-8")
        # /sync refuses a change-only workspace, so open the row the way /sync does: no declared role.
        open_source_row(PROJECT, folder / "sad-registrada.md", "synced", fallback_kind="technology_context")
        row = next(r for r in load_source_manifest(PROJECT)["registry"]
                   if any(p.endswith("02_technology_context/sad-registrada.md") for p in r["paths"]))
        self.assertNotIn("role", row)
        row_, findings = self.resolve(cite("00_raw/02_technology_context/sad-registrada.md"))
        self.assertEqual(row_["status"], "CLOSED", findings)

    def test_rejects_registered_row_without_a_role(self):
        folder = workspace_path(PROJECT) / "00_raw" / "04_quality_context"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "calidad.md").write_text(SAD_TEXT, encoding="utf-8")
        open_source_row(PROJECT, folder / "calidad.md", "synced")
        row, findings = self.resolve(cite("00_raw/04_quality_context/calidad.md"))
        self.assertEqual(row["status"], "ANSWERED")
        text = " ".join(findings)
        self.assertNotIn("None", text)
        self.assertIn("no está registrada como línea de base", text)

    def test_guide_mentions_role(self):
        text = change_gaps_path(workspace_path(PROJECT), "CHG-001").read_text(encoding="utf-8")
        self.assertIn("--role linea_de_base", text)


if __name__ == "__main__":
    unittest.main()
