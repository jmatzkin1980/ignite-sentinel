"""IMP-334: `/validate` and `/export --final` count the same pending marks."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.deliverables import DeliverableNotReady, gate
from sentinel.pending_marks import count_pending_marks
from sentinel.validation import score_artifact_text, semantic_quality_report

# A brief v2 with 3 real client marks and 1 domain mark in the body, plus a legend
# that names the vocabulary and summary tables that index the marks.
BRIEF_V2 = "\n".join([
    "<!-- sentinel-artifact: v2 -->",
    "# Project Brief — X",
    "",
    "## 0. Header",
    "",
    "### 0.1 How to read this brief",
    "",
    "- ⏳ PENDING (gap): the client owes this data; it blocks.",
    "- ⏳ PENDING DOMAIN (gap): domain context owes it; it can be deferred.",
    "",
    "### 0.2 Status",
    "",
    "| Section | Facts | ⏳ client | ⏳ domain | N/A |",
    "|---|---|---|---|---|",
    "| 1 | 0 | 3 | 1 | 0 |",
    "",
    "Ready to build: no. 3 pending marks block (§7).",
    "",
    "## 1. Identity and value",
    "",
    "### 1.1 Identity",
    "",
    "⏳ PENDING (GAP-USERS)",
    "",
    "### 1.2 Problem",
    "",
    "⏳ PENDING (GAP-OBJECTIVE)",
    "",
    "### 1.3 KPI",
    "",
    "- The KPI is lead time. ⏳ PENDING (GAP-METRIC-SOURCE)",
    "",
    "### 1.4 Constraints",
    "",
    "⏳ PENDING DOMAIN (GAP-GOVERNANCE-CONSTRAINTS)",
    "",
    "## 7. Dependencies",
    "",
    "### 7.2 Seeded marks",
    "",
    "3 client marks (block) and 1 domain marks (deferrable) in the body.",
    "",
    "| Place | Class | Gap |",
    "|---|---|---|",
    "| 1.1/identity | ⏳ PENDING client | `GAP-USERS` |",
    "| 1.2/problem | ⏳ PENDING client | `GAP-OBJECTIVE` |",
    "| 1.3/kpi | ⏳ PENDING client | `GAP-METRIC-SOURCE` |",
    "| 1.4/constraints | ⏳ PENDING DOMAIN | `GAP-GOVERNANCE-CONSTRAINTS` |",
    "",
]) + "\n"

REPORT = {
    "brief_version": 2,
    "fill_sites": [
        {"id": "1.1/identity", "class": "client", "gap": "GAP-USERS"},
        {"id": "1.2/problem", "class": "client", "gap": "GAP-OBJECTIVE"},
        {"id": "1.3/kpi", "class": "client", "gap": "GAP-METRIC-SOURCE"},
        {"id": "1.4/constraints", "class": "domain", "gap": "GAP-GOVERNANCE-CONSTRAINTS"},
    ],
}


def _workspace(tmp: str, report: dict | None) -> Path:
    base = Path(tmp)
    folder = base / "02_requirements"
    folder.mkdir(parents=True)
    (folder / "project-brief.md").write_text(BRIEF_V2, encoding="utf-8")
    if report is not None:
        (folder / "brief_compile_report.json").write_text(json.dumps(report), encoding="utf-8")
    return base


class CountTests(unittest.TestCase):
    def test_brief_v2_text_counts_body_marks_only(self):
        marks = count_pending_marks(BRIEF_V2)
        self.assertEqual((marks.blocking, marks.deferred), (3, 1))
        self.assertEqual(marks.source, "text")

    def test_brief_v2_prefers_the_compile_report(self):
        marks = count_pending_marks(BRIEF_V2, REPORT)
        self.assertEqual((marks.blocking, marks.deferred, marks.source), (3, 1, "compile_report"))
        # the report is the brief's own count, even when the text quotes a mark-like string
        quoted = BRIEF_V2 + "\n- The source says \"⏳ PENDING\" verbatim [[sources § Log # SRC-1 — supports: 1.1]]\n"
        self.assertEqual(count_pending_marks(quoted, REPORT).blocking, 3)

    def test_v1_marks_all_block(self):
        text = "# PRD\n\n- [PENDING INPUT]\n- [PENDING DOMAIN CONTEXT]\n- ⏳ PENDING (GAP-Y)\n- [POR COMPLETAR]\n"
        marks = count_pending_marks(text)
        self.assertEqual((marks.blocking, marks.deferred), (4, 0))


class AgreementTests(unittest.TestCase):
    def test_validate_and_export_report_the_same_count(self):
        for report in (None, REPORT):
            with self.subTest(report=bool(report)), tempfile.TemporaryDirectory() as tmp:
                base = _workspace(tmp, report)
                quality, warnings = semantic_quality_report(base)
                self.assertEqual(quality["project-brief.md"]["pending_markers"], 3)
                self.assertEqual(quality["project-brief.md"]["deferred_markers"], 1)
                self.assertTrue(any("3 pending markers" in w for w in warnings))
                verdict = gate(BRIEF_V2, artifact="brief", fmt="md", final=False, report=report)
                self.assertEqual(verdict["pending_marks"], 3)
                with self.assertRaises(DeliverableNotReady) as refused:
                    gate(BRIEF_V2, artifact="brief", fmt="md", final=True, report=report)
                self.assertIn("3 pending marks remain", str(refused.exception))

    def test_export_final_reads_the_compile_report(self):
        from sentinel.export import export_artifact

        with tempfile.TemporaryDirectory() as tmp:
            base = _workspace(tmp, {**REPORT, "fill_sites": REPORT["fill_sites"][:2]})
            with patch("sentinel.export.workspace_path", lambda _pid: base):
                with self.assertRaises(DeliverableNotReady) as refused:
                    export_artifact("X", "brief", "md", final=True)
        self.assertIn("2 pending marks remain", str(refused.exception))

    def test_score_counts_v2_marks(self):
        score = score_artifact_text(BRIEF_V2)
        self.assertEqual(score["pending_markers"], 3)
        self.assertEqual(score["classification"], "scaffolding")


if __name__ == "__main__":
    unittest.main()
