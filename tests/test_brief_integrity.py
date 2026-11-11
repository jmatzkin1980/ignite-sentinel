"""IMP-255: one finding per seeded case, none on a clean v2 brief or on v1."""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.brief_integrity import (
    brief_v2_integrity_findings,
    mark_findings,
    report_findings,
    value_findings,
    vocabulary_problems,
)
from sentinel.compilers.brief_v2 import render_brief_v2

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from test_brief_v2_compiler import inputs  # noqa: E402

MARKER = "<!-- sentinel-artifact: v2 -->"


def clean():
    assumptions = [{"id": "ASM-FLOW", "statement": "A single screen lists the queues.", "status": "ASSUMED",
                    "closes_gap": "GAP-DESIGN-FLOW"}]
    gap_rows = [{"id": "GAP-OBJECTIVE", "severity": "high", "status": "OPEN", "origin": ""},
                {"id": "GAP-DESIGN-FLOW", "severity": "high", "status": "OPEN", "origin": ""},
                {"id": "GAP-CONTRA-FEE", "severity": "high", "status": "OPEN", "origin": "contradiction"},
                {"id": "GAP-ACCEPTANCE", "severity": "high", "status": "CLOSED", "origin": ""}]
    contradiction = [{"gap": "GAP-CONTRA-FEE", "scope": "business", "value": "The fee is 2 percent.",
                      "source": "F-01", "resolved": True}]
    text, report = render_brief_v2(inputs(assumptions=assumptions, gaps=gap_rows, contradictions=contradiction,
                                          validation_direction="built"))
    gaps = {row["id"]: dict(row) for row in gap_rows}
    for umbrella in report["umbrella_gaps"]:
        gaps[umbrella] = {"id": umbrella, "status": "OPEN", "origin": "checklist"}
    ledger = {"units": [{"id": f"KLU-BRIEF-{i:03d}", "status": "INFERRED",
                         "links": [{"type": "brief_place", "target": row["place"]},
                                   {"type": "assumption", "target": row["assumption"]}]}
                        for i, row in enumerate(report["inferred"], start=1)]}
    return text, report, gaps, ledger


def all_findings(text, report, gaps, ledger):
    return mark_findings(text, gaps) + report_findings(text, report, ledger) + value_findings(text)


class CleanBriefTests(unittest.TestCase):
    def test_a_compiled_brief_has_no_findings(self):
        self.assertEqual(all_findings(*clean()), [])
        spanish = render_brief_v2(inputs(language="es"))
        gaps = {"GAP-OBJECTIVE": {"status": "OPEN"}, **{u: {"status": "OPEN"} for u in spanish[1]["umbrella_gaps"]}}
        self.assertEqual(mark_findings(spanish[0], gaps) + value_findings(spanish[0]), [])


class SeededCaseTests(unittest.TestCase):
    def assertOneNew(self, mutate, needle):
        text, report, gaps, ledger = clean()
        text, report, gaps, ledger = mutate(text, report, gaps, ledger)
        findings = all_findings(text, report, gaps, ledger)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn(needle, findings[0])

    def test_mark_to_a_gap_that_does_not_exist(self):
        def mutate(text, report, gaps, ledger):
            del gaps["GAP-OBJECTIVE"]
            return text, report, gaps, ledger
        text, report, gaps, ledger = clean()
        del gaps["GAP-OBJECTIVE"]
        findings = mark_findings(text, gaps)
        self.assertTrue(findings)
        self.assertTrue(all("GAP-OBJECTIVE, which is not in gaps.md" in f for f in findings))

    def test_closed_gap_leaves_a_live_mark(self):
        text, report, gaps, ledger = clean()
        gaps["GAP-DESIGN-FLOW"]["status"] = "CLOSED"
        findings = mark_findings(text, gaps)
        self.assertEqual(len(findings), text.count("(GAP-DESIGN-FLOW)"), findings)
        self.assertTrue(all("GAP-DESIGN-FLOW is closed but its mark is still live" in f for f in findings))

    def test_divergence_mark_without_an_open_divergence(self):
        def mutate(text, report, gaps, ledger):
            gaps["GAP-CONTRA-FEE"]["origin"] = "checklist"
            return text, report, gaps, ledger
        self.assertOneNew(mutate, "⚠ points to GAP-CONTRA-FEE")

    def test_mark_without_fill_site_and_fill_site_without_mark(self):
        def drop_site(text, report, gaps, ledger):
            sites = list(report["fill_sites"])
            sites.remove(next(s for s in sites if s["gap"] == "GAP-CONTRA-FEE" or s["id"] == "1.2"))
            return text, {**report, "fill_sites": sites}, gaps, ledger
        self.assertOneNew(drop_site, "has no fill site")

        def extra_site(text, report, gaps, ledger):
            report = {**report, "fill_sites": report["fill_sites"] + [{"id": "3.4", "gap": "GAP-OBJECTIVE"}]}
            return text, report, gaps, ledger
        self.assertOneNew(extra_site, "fill site for GAP-OBJECTIVE has no mark")

    def test_inference_without_its_ledger_row(self):
        self.assertOneNew(lambda t, r, g, l: (t, r, g, {"units": []}), "ASM-FLOW has no INFERRED row")

    def test_forbidden_values(self):
        cases = {
            "- Owner: -": "forbidden value '-'",
            "- —": "forbidden value '—'",
            "- Integrations: ninguno": "forbidden value 'ninguno'",
            "| 3.4 |  | `GAP-OBJECTIVE` |": "table cell holds a forbidden value",
            "N/A": "N/A without its reason",
            "The rollout date is TBD.": "the brief's own TBD",
        }
        for line, needle in cases.items():
            with self.subTest(line=line):
                self.assertOneNew(lambda t, r, g, l, line=line: (t.replace("### 2.3 ", f"{line}\n\n### 2.3 ", 1), r, g, l),
                                  needle)

    def test_explicit_nothing_is_allowed(self):
        text, report, gaps, ledger = clean()
        text = text.replace("### 2.3 ", "- Blocked by: nada\n- Integrations: none\n\n### 2.3 ", 1)
        self.assertEqual(all_findings(text, report, gaps, ledger), [])

    def test_source_tbd_inside_a_citation_is_not_the_briefs_own(self):
        text, report, gaps, ledger = clean()
        text = text.replace("### 2.3 ", "- Date TBD. [[sources § Source log - V2_PURE # F-01 — supports: x]]\n\n### 2.3 ", 1)
        self.assertEqual(value_findings(text), [])

    def test_edit_residues(self):
        for line in ("Last updated: the rollout moved.", "Antes decía que eran dos pantallas.",
                     "This document was updated after the workshop.", "The scope [edit] grew."):
            with self.subTest(line=line):
                self.assertOneNew(lambda t, r, g, l, line=line: (t.replace("### 2.3 ", f"{line}\n\n### 2.3 ", 1), r, g, l),
                                  "edit residue")


class GatingTests(unittest.TestCase):
    def test_v1_briefs_are_never_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "02_requirements").mkdir()
            for language in ("en", "es"):
                golden = (ROOT / "fixtures" / "golden" / language / "project-brief.md").read_text(encoding="utf-8")
                (base / "02_requirements" / "project-brief.md").write_text(golden, encoding="utf-8")
                self.assertEqual(brief_v2_integrity_findings(base), [])

    def test_vocabulary_variants(self):
        self.assertEqual(vocabulary_problems(f"{MARKER}\n⏳ PENDING (GAP-X) and ⏳ PENDIENTE DOMINIO (GAP-Y)", MARKER), [])
        self.assertEqual(vocabulary_problems("`⏳` PENDING (gap) is the legend style", MARKER), [])
        problems = vocabulary_problems("<!-- sentinel-artifact:v2 -->\n⏳PENDING (GAP-X)\n⏳ pending (GAP-Y)", MARKER)
        self.assertEqual(len(problems), 3, problems)

    def test_repository_skills_use_the_canonical_vocabulary(self):
        from sentinel.doctor import brief_vocabulary_check

        self.assertEqual(brief_vocabulary_check(ROOT.parent)["status"], "PASS")


class WorkspaceTests(unittest.TestCase):
    def test_compiled_workspace_brief_is_clean_and_validate_reports_a_seeded_residue(self):
        from sentinel.cli import main
        from sentinel.memory import ContextBroker
        from sentinel.validation import validate_project
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["es"]
        pid = "BRIEF_V2_INTEGRITY"
        old_cwd = Path.cwd()
        tmp = Path(tempfile.mkdtemp())
        os.chdir(tmp)
        try:
            with patch.object(ContextBroker, "_connect_lancedb", lambda self: None), \
                    contextlib.redirect_stdout(io.StringIO()):
                raw = tmp / "raw.md"
                raw.write_text(scenario["raw"], encoding="utf-8")
                self.assertEqual(main(["init", pid, "--brief-version", "1"]), 0)
                self.assertEqual(main(["ingest", pid, "--source", str(raw)]), 0)
                for index, statement in enumerate(scenario["ears"], start=1):
                    answer = tmp / f"answer-{index}.md"
                    answer.write_text(scenario["answer"].format(s=statement, i=index), encoding="utf-8")
                    self.assertEqual(main(["resolve-gaps", pid, "--source", str(answer)]), 0)
                self.assertEqual(main(["brief", pid, "--brief-version", "2", "--profile", "UI,BAT",
                                       "--genesis", "greenfield"]), 0)
                base = tmp / "workspaces" / pid
                self.assertEqual(brief_v2_integrity_findings(base), [])
                brief = base / "02_requirements" / "project-brief.md"
                brief.write_text(brief.read_text(encoding="utf-8").replace(
                    "### 2.3 ", "Última actualización: se sumó un rol.\n\n### 2.3 ", 1), encoding="utf-8")
                result = validate_project(pid)
            self.assertEqual(result["verdict"], "INVALID")
            self.assertTrue(any("edit residue" in finding for finding in result["findings"]))
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
