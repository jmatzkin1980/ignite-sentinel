"""Tests for EARS requirement normalization (IMP-026).

- classify_ears recognizes the five EARS patterns (EN + ES) and rejects prose.
- When a functional gap closes with a substantive answer already written in EARS
  syntax, /resolve-gaps accumulates it into requirements.md as a REQ-EARS-* row
  with its pattern and source; a prose answer is NOT normalized (invariant #3).
"""
from __future__ import annotations

import os
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.compilers.backlog import render_epic
from sentinel.compilers.specs import render_specs
from sentinel.discovery import parse_gap_rows
from sentinel.ears import classify_ears, is_ears, requirements_quality_report, score_requirement_quality
from sentinel.gap_resolution import resolve_gaps
from sentinel.generation import parse_ears_requirements
from sentinel.generation import render_epic as generation_render_epic
from sentinel.generation import render_specs as generation_render_specs

RAW = (
    "# Ops Dashboard\n\n"
    "We need a dashboard for the operations team to see queue risk.\n"
)


class EarsClassifyTests(unittest.TestCase):
    def test_patterns(self):
        self.assertEqual(classify_ears("The system shall display the queue."), "ubiquitous")
        self.assertEqual(classify_ears("When a case breaches SLA, the system shall flag it."), "event")
        self.assertEqual(classify_ears("While data is stale, the dashboard shall warn."), "state")
        self.assertEqual(classify_ears("If the service is down, then the system shall show riskUnknown."), "unwanted")
        self.assertEqual(classify_ears("Where audit logging is enabled, the system shall record access."), "optional")
        self.assertEqual(classify_ears("Cuando un caso supera el SLA, el sistema debe marcarlo."), "event")

    def test_prose_is_not_ears(self):
        self.assertIsNone(classify_ears("We want a nice dashboard."))
        self.assertFalse(is_ears("Reduce manual work by 30%."))

    def test_requirement_quality_distinguishes_vague_from_testable(self):
        vague = score_requirement_quality("We need a nice dashboard soon that is easy and efficient.")
        self.assertLess(vague["score"], 0.55)
        self.assertEqual(vague["classification"], "weak")
        signal_ids = {item["id"] for item in vague["signals"]}
        self.assertIn("ambiguous_term", signal_ids)
        self.assertIn("not_ears_normalizable", signal_ids)
        self.assertIn("missing_verification", signal_ids)
        self.assertTrue(all(item["fragment"] for item in vague["signals"]))

        testable = score_requirement_quality(
            "When a case breaches SLA, the system shall flag the queue within 5 minutes."
        )
        self.assertEqual(testable["classification"], "testable")
        self.assertEqual(testable["ears_pattern"], "event")
        self.assertEqual(testable["signals"], [])

        passive = score_requirement_quality("The alert shall be displayed when the queue is stale.")
        self.assertIn("passive_voice", {item["id"] for item in passive["signals"]})

    def test_requirement_quality_flags_compound_statement(self):
        result = score_requirement_quality(
            "When expense submitted, system shall validate amount and notify approver within 5 minutes."
        )
        signal_ids = {item["id"] for item in result["signals"]}
        self.assertIn("compound_statement", signal_ids)
        self.assertNotIn("missing_verification", signal_ids)
        compound = next(item for item in result["signals"] if item["id"] == "compound_statement")
        self.assertEqual(compound["category"], "scope")
        self.assertIn("Why it matters", compound["message"])
        self.assertIn("why_it_matters", compound)

    def test_requirement_quality_does_not_treat_nominal_list_as_compound(self):
        result = score_requirement_quality(
            "When dashboard opens, system shall show ticket volume, resolution time, and backlog ageing within 5 seconds."
        )
        self.assertNotIn("compound_statement", {item["id"] for item in result["signals"]})

    def test_requirement_quality_flags_unanchored_quantifier_separately(self):
        result = score_requirement_quality("The system shall load reports quickly and support various filters.")
        signals = result["signals"]
        signal_ids = {item["id"] for item in signals}
        self.assertIn("unanchored_quantifier", signal_ids)
        quantifier_fragments = [
            item["fragment"] for item in signals if item["id"] == "unanchored_quantifier"
        ]
        self.assertTrue(any("various" in fragment for fragment in quantifier_fragments))
        self.assertFalse(
            any(item["id"] == "ambiguous_term" and "various" in item["fragment"] for item in signals)
        )
        categories = {
            item["category"] for item in signals if item["id"] == "unanchored_quantifier"
        }
        self.assertIn("temporal", categories)
        self.assertIn("quantity", categories)

    def test_requirement_quality_allows_vague_term_with_nearby_numeric_anchor(self):
        result = score_requirement_quality("When report opens, system shall load fast within 2 seconds.")
        self.assertNotIn("unanchored_quantifier", {item["id"] for item in result["signals"]})

    def test_requirement_quality_explains_ambiguous_terms_by_category(self):
        result = score_requirement_quality("The system shall provide a nice dashboard.")
        ambiguous = next(item for item in result["signals"] if item["id"] == "ambiguous_term")
        self.assertEqual(ambiguous["severity"], "medium")
        self.assertEqual(ambiguous["category"], "subjective")
        self.assertIn("Why it matters", ambiguous["message"])
        self.assertIn("observable criteria", ambiguous["why_it_matters"])
        self.assertIn("nice", ambiguous["fragment"])

    def test_requirements_markdown_quality_scores_primary_and_ears_rows(self):
        report = requirements_quality_report(
            "# Requirement Register - DEMO\n\n"
            "## REQ-001 Primary Requirement\n\n"
            "- Source: `RAW-001`\n"
            "- Status: `draft`\n"
            "- Domains: product, functional, quality\n\n"
            "We need something better soon.\n\n"
            "## Normalized Requirements (EARS)\n\n"
            "| ID | Pattern | Statement | Source |\n"
            "| --- | --- | --- | --- |\n"
            "| REQ-EARS-001 | event | When a case breaches SLA, the system shall flag it. | `GAP-001` / `CHG-001` |\n"
        )
        self.assertEqual(report["statement_count"], 2)
        self.assertLess(report["score"], 1.0)
        self.assertEqual(report["statements"][0]["id"], "REQ-001")
        self.assertEqual(report["statements"][1]["id"], "REQ-EARS-001")
        self.assertTrue(report["warnings"])


class EarsResolutionTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        src = self.temp / "raw.md"
        src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "EARS"]), 0)
        self.assertEqual(main(["ingest", "EARS", "--source", str(src)]), 0)
        self.ws = self.temp / "workspaces" / "EARS"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _first_two_gap_ids(self):
        gaps = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        ids = [g["id"] for g in gaps if g["id"] != "NONE"]
        return ids[:2]

    def test_ears_answer_normalized_prose_not(self):
        ids = self._first_two_gap_ids()
        self.assertGreaterEqual(len(ids), 2, "fixture should produce at least two gaps")
        ears_gap, prose_gap = ids[0], ids[1]
        ears_stmt = "When a case breaches its SLA, the system shall flag the queue as high risk."
        answered = self.temp / "answers.md"
        answered.write_text(
            f"### {ears_gap} - x\n"
            f"- Answer: {ears_stmt}\n- Owner / source: Ops\n- Evidence or reference: Workshop\n- Decision status: confirmed\n\n"
            f"### {prose_gap} - y\n"
            f"- Answer: The team reviews queues every morning before standup.\n- Owner / source: Ops\n- Evidence or reference: Workshop\n- Decision status: confirmed\n",
            encoding="utf-8",
        )
        resolve_gaps("EARS", answered)
        req = (self.ws / "02_requirements" / "requirements.md").read_text(encoding="utf-8")
        self.assertIn("## Normalized Requirements (EARS)", req)
        self.assertIn("REQ-EARS-001", req)
        self.assertIn("| event |", req)
        self.assertIn(ears_stmt, req)
        self.assertIn(f"`{ears_gap}`", req)
        # The prose answer must NOT be normalized.
        self.assertNotIn("reviews queues every morning", req)


class EarsDownstreamCitationTests(unittest.TestCase):
    def test_generation_render_epic_import_remains_compatible(self):
        self.assertIs(generation_render_epic, render_epic)

    def test_generation_render_specs_import_remains_compatible(self):
        self.assertIs(generation_render_specs, render_specs)

    def test_specs_and_backlog_cite_confirmed_ears_rows(self):
        req_text = (
            "# Requirements\n\n"
            "## Normalized Requirements (EARS)\n\n"
            "| ID | Pattern | Statement | Source |\n"
            "| --- | --- | --- | --- |\n"
            "| REQ-EARS-001 | event | When a case breaches SLA, the system shall flag the queue. | `GAP-001` / `CHG-001` |\n"
        )
        ears = parse_ears_requirements(req_text)
        self.assertEqual(ears[0]["id"], "REQ-EARS-001")
        context = {"ears_requirements": ears, "sections": {}}

        specs = render_specs("EARS", "Mature requirement", context, "requirements.md")
        self.assertIn("## Confirmed EARS Requirements", specs)
        self.assertIn("`REQ-EARS-001`", specs)
        self.assertIn("cite the relevant `REQ-EARS-*` IDs", specs)

        epic = render_epic("EARS", [], context)
        self.assertIn("  - REQ-EARS-001", epic)
        self.assertIn("## Confirmed EARS Requirements", epic)
        self.assertIn("When a case breaches SLA", epic)

    def test_requirement_schema_supports_ears_metadata(self):
        schema = json.loads(Path("sentinel/schemas/requirement.schema.json").read_text(encoding="utf-8"))
        pattern = schema["properties"]["id"]["pattern"]
        self.assertIsNotNone(re.match(pattern, "REQ-001"))
        self.assertIsNotNone(re.match(pattern, "REQ-EARS-001"))
        ears = schema["properties"]["ears"]
        self.assertIn("pattern", ears["required"])
        self.assertIn("event", ears["properties"]["pattern"]["enum"])


if __name__ == "__main__":
    unittest.main()
