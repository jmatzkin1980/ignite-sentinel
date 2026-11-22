"""IMP-398 (H26 inc 1): the change path stops giving false completeness signals.

A mature, long request used to leave the change brief saying "no open question: the change note covers it"
and `/next` ending in "Change up to date", although none of the request's rules or criteria reached the
brief. These tests pin the honest signals; none of them adds an extraction capability.
"""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from test_change_brief_cli import run_err  # noqa: E402
from sentinel.changes import change_gaps_path, get_change  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.pending_marks import count_pending_marks  # noqa: E402
from sentinel.readiness_verdict import CHANGE_COMMANDS, CHANGE_TEXT, change_next_step  # noqa: E402
from sentinel.workspace import read_json, update_state, workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402
from test_change_next import set_change  # noqa: E402
from test_change_specs import ALL_ANSWERS  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CID = "CHG-001"
OLD_ES = "la nota del cambio lo cubre"
OLD_EN = "the change note covers it"


def brief_text(project: str) -> str:
    return (workspace_path(project) / "02_requirements" / CID / "project-brief.md").read_text(encoding="utf-8")


def brief_report(project: str) -> dict:
    return json.loads((workspace_path(project) / "02_requirements" / CID / "change_brief_report.json").read_text(encoding="utf-8"))


def section(text: str, number: int) -> str:
    return text.split(f"## {number}.", 1)[1].split("\n## ", 1)[0]


class Mature(SnapshotWorkspaceCase):
    """A mature request (objective, users, process, rules and criteria all explicit) walked to the brief."""

    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_mature" / "pedido_maduro.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "MAD"])
        run_ok(["ingest", "MAD", "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", "MAD", "--source", "scope.md", "--change", CID])
        run_ok(["brief", "MAD", "--change", CID])

    def test_mature_request_brief_shows_pending_extraction_not_note_covers(self):
        text = brief_text("MAD")
        self.assertNotIn(OLD_ES, text)
        self.assertNotIn("Sin pregunta abierta", text)
        for number in (2, 4):
            body = section(text, number)
            self.assertIn("⏳ PENDIENTE DE EXTRACCIÓN: el pedido trata este tema y todavía no está en el brief", body)
        self.assertEqual(brief_report("MAD")["extraction_pending"], ["2", "4"])
        self.assertIn("extracción pendiente: §2, §4", section(text, 9))
        # the lens round opened no functional question: the request's rules and criteria are not asked anywhere
        rows = parse_gap_rows(change_gaps_path(workspace_path("MAD"), CID).read_text(encoding="utf-8"))
        ids = {row["id"] for row in rows}
        self.assertFalse(ids & {"GAP-ACCEPTANCE", "GAP-BUSINESS-RULES", "GAP-PRD-FR-AC"})

    def test_pending_extraction_counts_as_deferred(self):
        text = brief_text("MAD")
        marks = count_pending_marks(text)
        self.assertEqual(marks.blocking, brief_report("MAD")["blocking_open"])
        self.assertGreaterEqual(marks.deferred, 2)
        mark_es = "⏳ PENDIENTE DE EXTRACCIÓN: el pedido trata este tema y todavía no está en el brief (`x`)"
        mark_en = "⏳ PENDING EXTRACTION: the request covers this and it is not in the brief yet (`x`)"
        v2 = "<!-- sentinel-artifact: v2 -->\n\n## 2. Reglas\n\n"
        for mark in (mark_es, mark_en):
            counted = count_pending_marks(v2 + f"- {mark}\n")
            self.assertEqual((counted.blocking, counted.deferred), (0, 1), mark)
        # existing marks keep their class
        self.assertEqual(count_pending_marks(v2 + "- ⏳ PENDIENTE (GAP-X)\n").blocking, 1)
        self.assertEqual(count_pending_marks(v2 + "- ⏳ PENDIENTE DOMINIO (GAP-X)\n").deferred, 1)
        # from a compile report: a domain-class site is deferred
        report = {"fill_sites": [{"id": "a", "class": "domain"}, {"id": "b", "class": "client"}]}
        self.assertEqual((count_pending_marks(v2, report).blocking, count_pending_marks(v2, report).deferred), (1, 1))
        # a draft export is not blocked and reports the deferred marks
        out = json.loads(run_ok(["export", "MAD", "--artifact", "brief", "--change", CID]))
        self.assertGreaterEqual(out["deferred_marks"], 2)

    def test_next_not_done_with_pending_extraction(self):
        s = change_next_step("MAD", CID)
        self.assertEqual(s["key"], "requirements")
        # Past requirements/specs/backlog/validate, the brief's pending extraction is what is left, never "done".
        # The middle steps are patched on purpose: no real walk reaches pending_extraction today, by design (the
        # extraction that would empty it arrives in a later increment, and until then a brief holding the mark
        # stops at requirements).
        with patch("sentinel.change_requirements.load_change_ears", return_value=[{"delta": "ADDED"}]), \
                patch("sentinel.change_requirements.parse_delta", return_value="ADDED"), \
                patch("sentinel.compilers.change_backlog.specs_currency", return_value="current"), \
                patch("sentinel.readiness_verdict._backlog_behind", return_value=False), \
                patch("sentinel.change_validation.validate_change", return_value={"verdict": "VALID"}):
            changes = read_json(workspace_path("MAD") / "state.json", {})["changes"]
            changes[CID].update(specs={"x": 1}, backlog={"dropped_units": []})
            update_state("MAD", changes=changes)
            (workspace_path("MAD") / "03_specs" / CID).mkdir(parents=True, exist_ok=True)
            (workspace_path("MAD") / "03_specs" / CID / "specs.md").write_text("x", encoding="utf-8")
            s = change_next_step("MAD", CID)
            self.assertEqual(s["key"], "pending_extraction")
            self.assertEqual(s["command"], "")
            self.assertEqual(s["title"], "Pasar el contenido del pedido al brief")
            self.assertIn("el brief no tiene todavía el contenido del pedido en §2, §4", s["text"])
            self.assertIn("cada regla y criterio del pedido se carga respondiendo en EARS, con Delta y Superficie", s["text"])
            self.assertIn("llega en un próximo incremento", s["text"])
            # without pending extraction the same state is done
            report_path = workspace_path("MAD") / "02_requirements" / CID / "change_brief_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["extraction_pending"] = []
            report_path.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(change_next_step("MAD", CID)["key"], "done")

    def test_english_mature_brief_carries_english_mark(self):
        set_change("MAD", language="en")
        run_ok(["brief", "MAD", "--change", CID])
        text = brief_text("MAD")
        self.assertIn("⏳ PENDING EXTRACTION: the request covers this and it is not in the brief yet", section(text, 2))
        self.assertNotIn(OLD_EN, text)
        self.assertIn("extraction pending: §2, §4", section(text, 9))
        self.assertEqual(count_pending_marks(text).blocking, 0)

    def test_final_export_refused_with_pending_extraction(self):
        code, err = run_err(["export", "MAD", "--artifact", "brief", "--change", CID, "--final"])
        self.assertNotEqual(code, 0)
        self.assertIn("2 sección(es) del brief todavía sin extraer del pedido (§2, §4)", err)
        self.assertIn("Sentinel todavía no extrae solo el contenido del pedido", err)
        self.assertNotIn("domain marks", err)
        self.assertFalse((workspace_path("MAD") / "08_context_packs" / "exports" / f"{CID}-project-brief.md").exists())
        set_change("MAD", language="en")
        code, err = run_err(["export", "MAD", "--artifact", "brief", "--change", CID, "--final"])
        self.assertNotEqual(code, 0)
        self.assertIn("2 section(s) of the brief not yet extracted from the request (§2, §4)", err)

    def test_draft_export_shows_banner_with_sections(self):
        out = json.loads(run_ok(["export", "MAD", "--artifact", "brief", "--change", CID]))
        self.assertEqual(out["deliverable"], "draft")
        self.assertEqual(out["extraction_pending"], ["2", "4"])
        target = workspace_path("MAD") / "08_context_packs" / "exports" / f"{CID}-project-brief.md"
        text = target.read_text(encoding="utf-8")
        self.assertIn("BORRADOR", text)
        self.assertIn("Extracción pendiente del pedido: §2, §4.", text)

    def test_brief_compiled_before_the_border_does_not_say_pending_extraction(self):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_mature" / "pedido_maduro.md", root / "otro.md")
        other = json.loads(run_ok(["ingest", "MAD", "--source", "otro.md", "--change"]))["change_id"]
        run_ok(["brief", "MAD", "--change", other])
        report = json.loads((workspace_path("MAD") / "02_requirements" / other / "change_brief_report.json").read_text(encoding="utf-8"))
        self.assertTrue(report["extraction_pending"])
        self.assertEqual(change_next_step("MAD", other)["key"], "scope")

    def test_requirements_text_never_names_missing_gap(self):
        s = change_next_step("MAD", CID)
        self.assertEqual(s["key"], "requirements")
        self.assertIn("no tiene ninguna pregunta funcional abierta donde responder los requisitos", s["text"])
        self.assertIn("el pedido los trae pero Sentinel todavía no los extrae solo (llega en un próximo incremento)", s["text"])
        for gap_id in ("GAP-ACCEPTANCE", "GAP-BUSINESS-RULES", "GAP-PRD-FR-AC"):
            self.assertNotIn(gap_id, s["text"])

    def test_ingest_change_records_gap_counts(self):
        counts = get_change("MAD", CID)["gap_counts"]
        self.assertIsNotNone(counts)
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_mature" / "pedido_maduro.md", root / "otro.md")
        out = json.loads(run_ok(["ingest", "MAD", "--source", "otro.md", "--change"]))
        recorded = get_change("MAD", out["change_id"])["gap_counts"]
        self.assertEqual(recorded, out["gap_counts"])
        self.assertEqual(recorded["total"], 1)
        self.assertEqual(recorded["blocking_open"], 1)


class Borrador(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", CID])

    def test_lenses_text_does_not_send_to_gaps_md(self):
        s = change_next_step("BORR", CID)
        self.assertEqual(s["key"], "lenses")
        self.assertIn("respondelos en un archivo de respuestas (no en gaps.md, que lo genera Sentinel) "
                      f"y corré /resolve-gaps --change {CID}", s["text"])
        self.assertNotIn("01_discovery", s["text"])

    def test_requirements_text_names_only_open_eligible_gaps(self):
        rows = parse_gap_rows(change_gaps_path(workspace_path("BORR"), CID).read_text(encoding="utf-8"))
        open_ids = {row["id"] for row in rows if str(row["status"]).strip("`").upper() != "CLOSED"}
        with patch("sentinel.readiness_verdict._change_step_key", return_value="requirements"):
            text = change_next_step("BORR", CID)["text"]
        self.assertIn("GAP-ACCEPTANCE", text)
        self.assertIn("Delta", text)
        self.assertIn("Superficie", text)
        for gap_id in ("GAP-ACCEPTANCE", "GAP-BUSINESS-RULES", "GAP-PRD-FR-AC"):
            self.assertEqual(gap_id in text, gap_id in open_ids, gap_id)

    def test_done_text_says_coverage_not_measured(self):
        for language, expected in (("es", ("Piezas del cambio al día", "Sentinel todavía no mide qué parte del pedido quedó cubierta",
                                           "cada regla y criterio del pedido tenga su requisito o su descarte")),
                                   ("en", ("Change pieces up to date", "Sentinel does not yet measure how much of the request is covered",
                                           "each rule and criterion of the request has its requirement or its discard"))):
            set_change("BORR", language=language)
            with patch("sentinel.readiness_verdict._change_step_key", return_value="done"):
                s = change_next_step("BORR", CID)
            self.assertEqual(s["title"], expected[0])
            self.assertIn(expected[1], s["text"])
            self.assertIn(expected[2], s["text"])
            self.assertEqual(s["command"], "")
        self.assertNotIn("Cambio al día", json.dumps(CHANGE_TEXT, ensure_ascii=False))
        self.assertNotIn("Change up to date", json.dumps(CHANGE_TEXT))

    def test_english_change_texts(self):
        set_change("BORR", language="en")
        s = change_next_step("BORR", CID)
        self.assertEqual(s["key"], "lenses")
        self.assertIn("answer them in a responses file (not in gaps.md, which Sentinel generates)", s["text"])
        with patch("sentinel.readiness_verdict._change_step_key", return_value="pending_extraction"):
            with patch("sentinel.readiness_verdict._extraction_pending", return_value=["2", "7"]):
                s = change_next_step("BORR", CID)
        self.assertEqual(s["title"], "Move the request content into the brief")
        self.assertIn("the brief does not hold the request content yet in §2, §7", s["text"])
        self.assertIn("each rule and criterion of the request is loaded by answering one question of the change in EARS", s["text"])
        self.assertEqual(s["command"], "")
        with patch("sentinel.readiness_verdict._change_step_key", return_value="requirements"), \
                patch("sentinel.readiness_verdict._open_ears_gaps", return_value=[]):
            s = change_next_step("BORR", CID)
        self.assertIn("has no open functional question where the requirements can be answered", s["text"])

    def test_change_commands_of_the_new_steps(self):
        self.assertEqual(CHANGE_COMMANDS["pending_extraction"], "")
        self.assertEqual(CHANGE_COMMANDS["done"], "")
        self.assertEqual(set(CHANGE_COMMANDS), {"scope", "lenses", "brief", "requirements", "specs", "backlog", "validate",
                                                "pending_extraction", "done"})


if __name__ == "__main__":
    unittest.main()
