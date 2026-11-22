"""IMP-382: the change path end to end, and the workspace it leaves passes /doctor and /status."""
from __future__ import annotations

import json
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from sentinel.core.markdown import parse_frontmatter  # noqa: E402
from sentinel.changes import change_gaps_path, get_change  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.workspace import read_state, workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCOPE_ANSWER = "\n".join([
    "### GAP-SCOPE",
    "- Respuesta: Sólo el formulario de alta de proveedores.",
    "- Borde:",
    '  - nuevo | pantalla | Botón "Guardar borrador" en el alta de proveedores',
    '  - nuevo | pantalla | Listado "Mis borradores"',
    "  - adyacente | endpoint | Envío actual del alta de proveedores",
    "  - adyacente | dato | Tabla de proveedores",
    "  - preservado | proceso | Envío completo del alta",
    "- Owner / fuente: Jefa de Compras",
    "- Estado de decisión: confirmado",
    "",
])


SCOPE_TOTAL, LENS_TOTAL, BLOCKING = 4, 20, 3
# answers_ears.md: 2 event + 1 unwanted ADDED statements become units; 1 UNCHANGED statement is preserved.
SPEC_UNITS, SPEC_PRESERVED, SPEC_BY_DELTA = 3, 1, {"ADDED": 3}
# /backlog --change: one story per unit under the change's epic; the UNCHANGED row is each story's pass-to-pass criterion.
BACKLOG_STORIES, BACKLOG_EPIC, BACKLOG_PASS_TO_PASS = ["US-001", "US-002", "US-003"], "EPIC-CHG-001", "REQ-EARS-001"
# Seven lens gaps have a citable phrase in the synthetic baseline.
BASELINE_CLOSED = {
    "GAP-DELIVERY-READINESS",
    "GAP-TECH-NFR", "GAP-GOVERNANCE-CONSTRAINTS", "GAP-PRD-GLOSSARY-GOVERNANCE",
    "GAP-PRD-ROLLOUT-ENVIRONMENTS", "GAP-TECH-DEEP-DIVE-INPUT", "GAP-QUALITY",
}


class ChangeFlow(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "BORR"])

    def test_borrador_end_to_end(self):
        out = json.loads(run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"]))
        cid = out["change_id"]
        self.assertEqual(out["round"], "scope")
        self.assertEqual(out["gap_counts"]["total"], SCOPE_TOTAL)
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", cid])
        change = get_change("BORR", cid)
        self.assertEqual(change["round"], "lenses")
        counts = change["gap_counts"]
        self.assertEqual(counts["total"], LENS_TOTAL)
        self.assertEqual(counts["blocking_open"], BLOCKING)
        # 20 total = 19 open + 1 closed (GAP-SCOPE).
        self.assertEqual(counts["open"], LENS_TOTAL - 1)
        # Load the baseline and close seven lens gaps by citing it: open 19 -> 12, blocking stays 3.
        raw = workspace_path("BORR") / "00_raw"
        shutil.copy(FIXTURES / "change_baseline" / "sad-compras.md", raw / "02_technology_context" / "sad-compras.md")
        shutil.copy(FIXTURES / "change_baseline" / "manual-compras.md", raw / "01_business_context" / "manual-compras.md")
        shutil.copy(FIXTURES / "change_baseline" / "answers_baseline.md", Path.cwd() / "answers_baseline.md")
        res = json.loads(run_ok(["resolve-gaps", "BORR", "--source", "answers_baseline.md", "--change", cid]))
        self.assertEqual(set(res["closed"]), BASELINE_CLOSED)
        self.assertEqual(res["closure_findings"], [])
        after = get_change("BORR", cid)["gap_counts"]
        self.assertEqual((after["total"], after["open"], after["closed"]), (LENS_TOTAL, 12, 8))
        self.assertEqual(after["blocking_open"], BLOCKING)
        rows = parse_gap_rows(change_gaps_path(workspace_path("BORR"), cid).read_text(encoding="utf-8"))
        self.assertEqual({r["id"] for r in rows if r.get("closure_reason") == "by_baseline"}, BASELINE_CLOSED)
        # The same note on the project path asks more.
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "proyecto.md")
        run_ok(["init", "PROJ"])
        run_ok(["ingest", "PROJ", "--source", "proyecto.md"])
        project_total = read_state("PROJ")["gap_counts"]["total"]
        self.assertEqual(project_total, 27)
        self.assertGreater(project_total, counts["total"])
        # The change brief: 9 sections, the three blocking gaps listed in section 9.
        brief_out = json.loads(run_ok(["brief", "BORR", "--change", cid]))
        brief_path = workspace_path("BORR") / "02_requirements" / cid / "project-brief.md"
        self.assertTrue(brief_path.exists())
        brief_text = brief_path.read_text(encoding="utf-8")
        self.assertEqual(9, len(re.findall(r"^## ", brief_text, flags=re.M)))
        report = json.loads((workspace_path("BORR") / "02_requirements" / cid / "change_brief_report.json").read_text(encoding="utf-8"))
        self.assertEqual(3, report["blocking_open"])
        section9 = brief_text.split("## 9.", 1)[1]
        for gap_id in ("GAP-OBJECTIVE", "GAP-USERS", "GAP-ACCEPTANCE"):
            self.assertIn(gap_id, section9)
        self.assertEqual(cid, brief_out["change_id"])
        # The EARS answers (with Delta) close the blocking gaps; /specs --change writes the units of the change, no PRD.
        shutil.copy(FIXTURES / "change_baseline" / "answers_ears.md", Path.cwd() / "answers_ears.md")
        run_ok(["resolve-gaps", "BORR", "--source", "answers_ears.md", "--change", cid])
        self.assertEqual(get_change("BORR", cid)["gap_counts"]["blocking_open"], 0)
        run_ok(["brief", "BORR", "--change", cid])
        report = json.loads((workspace_path("BORR") / "02_requirements" / cid / "change_brief_report.json").read_text(encoding="utf-8"))
        self.assertEqual(0, report["blocking_open"])
        specs_out = json.loads(run_ok(["specs", "BORR", "--change", cid]))
        self.assertEqual(len(specs_out["units"]), SPEC_UNITS)
        self.assertEqual(len(specs_out["preserved"]), SPEC_PRESERVED)
        self.assertEqual(specs_out["report"]["by_delta"], SPEC_BY_DELTA)
        self.assertEqual(specs_out["units"], ["SPEC-U-001", "SPEC-U-002", "SPEC-U-003"])
        self.assertEqual(specs_out["preserved"], ["REQ-EARS-001"])
        reqs = (workspace_path("BORR") / "02_requirements" / cid / "requirements.md").read_text(encoding="utf-8")
        self.assertRegex(reqs, r"\| REQ-EARS-001 \| event \| UNCHANGED \| Cuando el usuario envía un alta completa, el sistema debe continuar validando todos los campos obligatorios\.")
        specs_md = (workspace_path("BORR") / "03_specs" / cid / "specs.md").read_text(encoding="utf-8")
        self.assertIn("continuar validando todos los campos obligatorios", specs_md.split("Comportamiento preservado", 1)[1])
        self.assertFalse((workspace_path("BORR") / "03_specs" / "prd.md").exists())
        # /backlog --change: three stories under EPIC-CHG-001; no project stories, so no change requests and nothing Stale.
        backlog_out = json.loads(run_ok(["backlog", "BORR", "--change", cid]))
        self.assertEqual(backlog_out["stories"], BACKLOG_STORIES)
        self.assertEqual(backlog_out["epic"], BACKLOG_EPIC)
        self.assertEqual(backlog_out["change_requests"], [])
        self.assertEqual(backlog_out["stale"], [])
        self.assertEqual(backlog_out["report"]["pass_to_pass"], [BACKLOG_PASS_TO_PASS])
        backlog_dir = workspace_path("BORR") / "04_backlog"
        self.assertTrue((backlog_dir / f"{BACKLOG_EPIC}.md").exists())
        for story_id, unit in zip(BACKLOG_STORIES, specs_out["units"]):
            story_text = (backlog_dir / f"{story_id}.md").read_text(encoding="utf-8")
            self.assertEqual(parse_frontmatter(story_text)["source_unit"], unit)
            pass_to_pass = re.findall(r"^\| AC-\d+-06 \| pass-to-pass \|.*$", story_text, flags=re.M)
            self.assertEqual(len(pass_to_pass), 1)
            self.assertIn(BACKLOG_PASS_TO_PASS, pass_to_pass[0])
        self.assertFalse((workspace_path("BORR") / "03_specs" / "prd.md").exists())
        # IMP-396: the finished change validates, has no pending step and raises no escalation warning.
        validate_out = json.loads(run_ok(["validate", "BORR", "--change", cid]))
        self.assertEqual(validate_out["verdict"], "VALID")
        self.assertEqual({c["id"]: c["status"] for c in validate_out["checks"]}, {
            "unit_citations": "PASS", "preserved_pass_to_pass": "PASS",
            "rows_have_surfaces": "PASS", "stories_inside_border": "PASS"})
        self.assertEqual(validate_out["warnings"], [])
        next_out = json.loads(run_ok(["next", "BORR", "--change", cid]))
        # IMP-398: `done` says the registered pieces are up to date, not that the request is covered; the fixture's
        # brief holds no pending-extraction mark, so the step before it (`pending_extraction`) is not shown.
        self.assertEqual(next_out["key"], "done")
        self.assertIn("todavía no mide", next_out["text"])
        self.assertEqual(next_out["warnings"], [])
        final_brief = (workspace_path("BORR") / "02_requirements" / cid / "project-brief.md").read_text(encoding="utf-8")
        self.assertNotIn("PENDIENTE DE EXTRACCIÓN", final_brief)
        self.assertIn(json.loads(run_ok(["doctor"]))["verdict"], {"PASS", "WARN"})
        status = json.loads(run_ok(["status", "BORR"]))
        self.assertEqual(status["project_id"], "BORR")


if __name__ == "__main__":
    unittest.main()
