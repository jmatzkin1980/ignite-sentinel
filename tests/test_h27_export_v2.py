"""IMP-406 (H27 inc 1) task 7: the change's deliverable in the project brief v2 format, its seal and the `export_final` step."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, class_deferred, complete_extraction, run_ok, waive_crosses, waive_coherence  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.compilers.brief_v2 import BriefInputs, render_brief_v2  # noqa: E402
from sentinel.compilers.change_deliverable import build_seal, change_profiles, row_lens, seal_lines  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.extraction.confirm import confirm_item  # noqa: E402
from sentinel.extraction.coverage import extraction_coverage  # noqa: E402
from sentinel.extraction.inventory import build_inventory  # noqa: E402
from sentinel.extraction.proposals import record_proposals  # noqa: E402
from sentinel.brief_schema import load_brief_schema  # noqa: E402
from sentinel.readiness_verdict import build_change_verdict  # noqa: E402
from sentinel.resources import read_package_json  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LARGO = FIXTURES / "change_extraction" / "pedido_largo.md"
EJEMPLO = FIXTURES / "change_extraction" / "propuestas_ejemplo.md"
PID = "FIN"
CID = "CHG-001"
HEADINGS_ES = ["## 0. Encabezado", "## 1. Overview", "## 2. Lente de Negocio", "## 3. Lente de Producto",
               "## 4. Lente de Diseño", "## 5. Lente Técnico", "## 6. Acuerdos del Release",
               "## 7. Dependencias y Cuestiones a Confirmar", "## 8. Supuestos", "## 9. Cosas a Construir"]
HEADINGS_EN = ["## 0. Header", "## 1. Overview", "## 2. Business Lens", "## 3. Product Lens", "## 4. Design Lens",
               "## 5. Technical Lens", "## 6. Release Agreements", "## 7. Dependencies and Open Questions",
               "## 8. Assumptions", "## 9. Things to Build"]


def source_lines() -> list[str]:
    return LARGO.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def place(text: str, sid: str) -> str:
    """The text of one numbered subsection of the v2 brief, up to the next heading."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"### {sid} "))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith(("## ", "### "))), len(lines))
    return "\n".join(lines[start:end])


def hu01_block() -> str:
    text = EJEMPLO.read_text(encoding="utf-8")
    return text.split("### RN-02", 1)[0]


class ExportCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(LARGO, root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        (root / "hu01.md").write_text(hu01_block(), encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(FIXTURES / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base", "--change", CID])
        waive_crosses(PID, CID)
        build_inventory(PID, CID)
        record_proposals(PID, CID, root / "hu01.md")
        confirm_item(PID, CID, "HU-01")
        complete_extraction(PID, CID, skip=("HU-01",))
        run_ok(["brief", PID, "--change", CID])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def export(self, *extra: str) -> str:
        """Export the change's brief; the exported text (`--final` needs the open questions classed first)."""
        if "--final" in extra:
            class_deferred(PID, CID)
        result = json.loads(run_ok(["export", PID, "--artifact", "brief", "--change", CID, *extra]))
        return Path(result["path"]).read_text(encoding="utf-8")

    def set_language(self, language: str) -> None:
        changes = {k: dict(v) for k, v in list_changes(PID).items()}
        changes[CID]["language"] = language
        update_state(PID, changes=changes)
        forget_read_snapshots()
        waive_coherence(PID, CID)  # the lens view is written in the language of the change (IMP-410)

    def internal_brief(self) -> str:
        return (workspace_path(PID) / "02_requirements" / CID / "project-brief.md").read_text(encoding="utf-8")

    def next_step(self) -> dict:
        return json.loads(run_ok(["next", PID, "--change", CID]))

    def final_export(self) -> dict:
        forget_read_snapshots()
        return list_changes(PID)[CID].get("final_export") or {}


class ProjectBriefUnchanged(unittest.TestCase):
    def inputs(self) -> BriefInputs:
        text = ("The goal is to approve vendor registrations inside the system. "
                "In scope: the approval queue. Out of scope: foreign vendors. "
                "Today the analyst prints the summary and walks it to be signed.")
        return BriefInputs(
            project_id="PRJ", language="en", profiles=["UI"], genesis="greenfield",
            raw_sources=[("F-01", "raw.md", text)],
            gaps=[{"id": "GAP-OBJECTIVE", "severity": "high", "status": "OPEN", "origin": "checklist"}],
            registry=[{"id": "F-01", "paths": ["00_raw/raw.md"], "validity": "current"}],
        )

    def test_project_brief_v2_unchanged(self):
        base = self.inputs()
        plain, report = render_brief_v2(base)
        explicit, _ = render_brief_v2(replace(base, title="", place_facts={}, place_blocks={}, empty_na={}))
        self.assertEqual(plain, explicit)
        self.assertEqual(plain.splitlines()[1], "# Project Brief — PRJ")
        self.assertIn("⏳ PENDING", plain)
        self.assertNotIn("the change does not touch this point", plain)
        self.assertGreater(report["summary"]["pending_client"], 0)

    def test_new_fields_change_only_what_they_say(self):
        base = self.inputs()
        plain, _ = render_brief_v2(base)
        changed, report = render_brief_v2(replace(
            base, title="A change",
            place_facts={"6.1": [{"text": "[new] screen — Queue", "source": "F-01", "gap": ""}]},
            place_blocks={"0.2": ["> **Status:** draft", ""]},
            empty_na={"reason": "the change does not touch this point", "condition": "the change border adds it"}))
        self.assertEqual(changed.splitlines()[1], "# A change")
        self.assertIn("> **Status:** draft", changed)
        self.assertIn("`C-02` [new] screen — Queue", changed)
        self.assertNotIn("⏳ PENDING (", changed)
        self.assertNotIn("GAP-BRIEF-S", changed)
        self.assertEqual(report["summary"]["pending_client"], 0)
        self.assertNotEqual(plain, changed)


class Deliverable(ExportCase):
    def test_v2_headings_in_order(self):
        text = self.export()
        lines = text.splitlines()
        marker = read_package_json("templates", "brief_v2.json")["artifact_marker"]
        self.assertEqual(lines[0], marker)
        self.assertTrue(lines[1].startswith("# Brief del cambio CHG-001 — "), lines[1])
        numbered = [line for line in lines if re.match(r"^## \d+\. ", line)]
        self.assertEqual(numbered, HEADINGS_ES)
        annexes = [f"## {a['id']} {a['title']['es']}" for a in load_brief_schema()["annexes"]]
        self.assertEqual([line for line in lines if line.startswith("## ") and line not in HEADINGS_ES], annexes)
        self.set_language("en")
        run_ok(["brief", PID, "--change", CID])
        english = self.export().splitlines()
        self.assertEqual([line for line in english if re.match(r"^## \d+\. ", line)], HEADINGS_EN)
        self.assertTrue(english[1].startswith("# Change brief CHG-001 — "), english[1])

    def test_final_seal(self):
        text = self.export("--final")
        coverage = extraction_coverage(PID, CID)
        verdict = build_change_verdict(PID, CID)
        self.assertIn("**Estado:** final", text)
        self.assertIn(f"**Cobertura:** {coverage['total']} de {coverage['total']} elementos del pedido", text)
        self.assertIn("**Supuestos:** 0", text)
        self.assertIn(f"**Veredicto:** {verdict['verdict']}", text)
        build, operational = verdict["deferred"]["construccion"], verdict["deferred"]["operativo"]
        self.assertIn(f"**Pendientes diferidos:** {build + operational} (construcción {build}, operativo {operational})", text)
        recorded = self.final_export()
        self.assertEqual(recorded["brief_sha"], hashlib.sha256((workspace_path(PID) / "02_requirements" / CID / "project-brief.md").read_bytes()).hexdigest()[:16])
        self.assertEqual(recorded["verdict"], verdict["verdict"])
        self.assertTrue(recorded["path"].endswith(f"{CID}-project-brief.md"), recorded)
        self.assertTrue(recorded["at"])

    def test_draft_has_no_final_seal(self):
        text = self.export()
        self.assertIn("**Estado:** borrador", text)
        self.assertNotIn("**Estado:** final", text)
        self.assertEqual(self.final_export(), {})

    def test_english_seal(self):
        self.set_language("en")
        run_ok(["brief", PID, "--change", CID])
        text = self.export("--final")
        coverage = extraction_coverage(PID, CID)
        self.assertIn("**Status:** final", text)
        self.assertIn(f"**Coverage:** {coverage['total']} of {coverage['total']} request elements", text)
        self.assertIn("**Assumptions:** 0", text)
        self.assertRegex(text, r"\*\*Deferred items:\*\* \d+ \(build \d+, operational \d+\)")
        self.assertIn("N/A", text)

    def test_places_and_tags(self):
        text = self.export()
        statement = "Cuando el analista envía un alta con monto mayor al umbral, el sistema debe pasarla a la bandeja de aprobaciones."
        design = place(text, "4.1")
        self.assertIn("[nuevo]", design)
        self.assertIn(statement, design)
        preserved = place(text, "6.2")
        self.assertIn("[preservado]", preserved)
        self.assertIn("Validación de CUIT", preserved)
        scope = place(text, "6.1")
        self.assertIn("[nuevo] pantalla — Bandeja de aprobaciones", scope)
        self.assertIn("[modificado] endpoint — Alta de proveedores", scope)
        item = next(line for line in text.splitlines() if line.startswith("- `C-01`"))
        self.assertIn("[nuevo] pantalla — Bandeja de aprobaciones", item)
        self.assertIn("REQ-EARS-", item)
        self.assertIn("Sin supuestos registrados.", place(text, "8.1"))
        for line in text.splitlines():
            self.assertNotIn("GAP-BRIEF-S", line)
            self.assertNotIn("⏳ PENDIENTE", line)
        self.assertIn("N/A — el cambio no toca este punto. Si el borde del cambio lo suma, se abre.", text)

    def test_export_keeps_verbatim_table(self):
        text = self.export()
        process = place(text, "3.2")
        lines = source_lines()
        for number in [85, *range(87, 99)]:
            self.assertIn(lines[number - 1], process.splitlines(), number)
        self.assertIn("texto literal del pedido", process)

    def test_internal_brief_unchanged(self):
        before = self.internal_brief()
        self.assertNotIn("[nuevo]", before)
        run_ok(["brief", PID, "--change", CID])
        self.assertEqual(self.internal_brief(), before)

    def test_open_questions_table_has_class_and_owner(self):
        text = self.export()
        table = place(text, "7.1")
        self.assertIn("| Pendiente | Clase | Bloquea | Responsable |", table)

    def test_profiles_follow_the_border(self):
        border = [{"type": "pantalla", "name": "A"}, {"type": "dato", "name": "B"}, {"type": "regla", "name": "C"}]
        self.assertEqual(change_profiles(border, {}), ["UI", "API"])
        self.assertEqual(change_profiles([{"type": "integracion", "name": "X"}], {}), ["INT"])
        self.assertEqual(change_profiles([{"type": "regla", "name": "C"}], {}), ["UI"])
        self.assertEqual(change_profiles(border, {"profiles": ["BAT"]}), ["BAT"])

    def test_row_lens_by_first_surface(self):
        template = read_package_json("templates", "change_brief.json")
        border = [{"type": "pantalla", "name": "Bandeja"}, {"type": "endpoint", "name": "Alta"}, {"type": "regla", "name": "Monto"}]
        self.assertEqual(row_lens({"surfaces": ["Bandeja", "Alta"]}, border, template), "design")
        self.assertEqual(row_lens({"surfaces": ["Alta"]}, border, template), "technical")
        self.assertEqual(row_lens({"surfaces": ["Monto"]}, border, template), "business")
        self.assertEqual(row_lens({"surfaces": []}, border, template), "business")
        self.assertEqual(row_lens({"surfaces": ["Desconocida"]}, border, template), "business")

    def test_seal_lines(self):
        seal = {"state": "final", "date": "2026-11-24", "covered": 49, "total": 49,
                "deferred": {"construccion": 0, "operativo": 0}, "assumptions": 0, "verdict": "READY"}
        self.assertEqual(seal_lines(seal, "es"), [
            "> **Estado:** final · **Fecha:** 2026-11-24 · **Veredicto:** READY",
            "> **Cobertura:** 49 de 49 elementos del pedido",
            "> **Pendientes diferidos:** 0 (construcción 0, operativo 0)",
            "> **Supuestos:** 0",
        ])
        self.assertEqual(seal_lines(seal, "en")[0], "> **Status:** final · **Date:** 2026-11-24 · **Verdict:** READY")
        self.assertEqual(build_seal(PID, CID, False, "en")["state"], "draft")


class FinalStep(ExportCase):
    def test_export_final_step(self):
        # the open questions default to construccion: NOT_READY, and the step points at /gaps --impact (I6)
        step = self.next_step()
        self.assertEqual(step["key"], "export_final", step)
        self.assertTrue(step["command"].startswith(f"/gaps {PID} --change {CID} --id GAP-"), step)
        self.assertIn("--impact IMPACT", step["command"])
        self.assertIn("NOT_READY", step["text"])
        class_deferred(PID, CID)
        forget_read_snapshots()
        step = self.next_step()
        self.assertEqual(step["key"], "export_final", step)
        self.assertEqual(step["command"], f"/export {PID} --artifact brief --change {CID} --final")
        self.assertEqual(step["title"], "Exportar el brief final")
        self.assertIn("project brief v2", step["text"])
        self.assertIn("pendiente(s) diferido(s)", step["text"])
        self.export("--final")
        forget_read_snapshots()
        self.assertEqual(self.next_step()["key"], "specs")
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertTrue(status["final_export_current"])
        self.assertEqual(status["final_export"]["verdict"], status["verdict"]["verdict"])
        self.set_language("en")
        run_ok(["brief", PID, "--change", CID])
        forget_read_snapshots()
        again = self.next_step()
        self.assertEqual(again["key"], "export_final", again)
        self.assertIn("Export the final brief", again["title"])
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertFalse(status["final_export_current"])

    def test_draft_export_does_not_close_the_step(self):
        self.export()
        forget_read_snapshots()
        self.assertEqual(self.next_step()["key"], "export_final")


if __name__ == "__main__":
    unittest.main()
