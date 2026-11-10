"""IMP-253b: in-place rewrite, inferences in the ledger, `built` marks and the
transcription rules of the brief v2."""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.brief_model import parse_brief
from sentinel.compilers.brief_v2 import render_brief_v2, transcribe, v2_self_correction_findings

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from test_brief_v2_compiler import inputs  # noqa: E402


def place(text: str, sid: str) -> str:
    model = parse_brief(text)
    section = model.sections[sid]
    return "\n".join(text.splitlines()[section.start:section.end])


class InPlaceRewriteTests(unittest.TestCase):
    def test_answer_replaces_the_raw_statement_which_moves_to_provenance(self):
        answers = [{"gap": "GAP-USERS", "statement": "Team leads and analysts read the dashboard.", "source": "F-02"}]
        text, report = render_brief_v2(inputs(gap_answers=answers))
        users = place(text, "2.1")
        self.assertIn("Team leads and analysts read the dashboard. (`GAP-USERS`)", users)
        self.assertNotIn("Users: operations leads.", users)
        provenance = place(text, "A.provenance")
        self.assertIn("| 2.1 | Users: operations leads. | `F-01` | `GAP-USERS` |", provenance)
        self.assertIn({"place": "2.1", "statement": "Users: operations leads.", "source": "F-01", "by": "GAP-USERS"},
                      report["replaced"])
        self.assertTrue(all(row["place"] == "2.1" for row in report["replaced"]))

    def test_self_correction_gate_checks_each_answer_in_its_place(self):
        answers = [{"gap": "GAP-USERS", "statement": "Team leads and analysts read the dashboard.", "source": "F-02"}]
        text, _ = render_brief_v2(inputs(gap_answers=answers))
        criteria = {"GAP-USERS": {"statement": "Team leads and analysts read the dashboard.", "source": "CHG-001"}}
        self.assertEqual(v2_self_correction_findings(text, criteria), [])
        moved = text.replace("- Team leads and analysts read the dashboard. (`GAP-USERS`)", "-")
        moved += "\nTeam leads and analysts read the dashboard. GAP-USERS\n"
        findings = v2_self_correction_findings(moved, criteria)
        self.assertEqual(len(findings), 1)
        self.assertIn("§2.1", findings[0])


class InferenceTests(unittest.TestCase):
    def test_assumption_is_an_inference_beside_its_pending_mark(self):
        assumptions = [
            {"id": "ASM-FLOW", "statement": "A single screen lists the queues.", "status": "ASSUMED", "closes_gap": "GAP-DESIGN-FLOW"},
            {"id": "ASM-GONE", "statement": "Mobile first.", "status": "OPEN", "closes_gap": "GAP-DESIGN-PROTOTYPE-INPUT"},
        ]
        gaps = [{"id": "GAP-DESIGN-FLOW", "severity": "high", "status": "OPEN", "origin": ""}]
        text, report = render_brief_v2(inputs(assumptions=assumptions, gaps=gaps))
        flow = place(text, "4.1")
        self.assertIn("- (inferred) A single screen lists the queues. (`ASM-FLOW`)", flow)
        self.assertIn("⏳ PENDING (GAP-DESIGN-FLOW)", flow)
        self.assertNotIn("Mobile first.", place(text, "4.3"))
        self.assertEqual(report["summary"]["inferred"], 1)
        self.assertEqual(report["inferred"], [{"place": "4.1", "assumption": "ASM-FLOW",
                                               "statement": "A single screen lists the queues.", "gap": "GAP-DESIGN-FLOW"}])
        self.assertIn("| 4.1 | `ASM-FLOW` | `GAP-DESIGN-FLOW` |", place(text, "A.provenance"))
        spanish, _ = render_brief_v2(inputs(assumptions=assumptions, gaps=gaps, language="es"))
        self.assertIn("- (inferido) A single screen lists the queues.", spanish)


class BuiltDirectionTests(unittest.TestCase):
    contradiction = [{"gap": "GAP-CONTRA-FEE", "scope": "business", "value": "The fee is 2 percent.",
                      "source": "F-01", "resolved": True}]
    gaps = [{"id": "GAP-CONTRA-FEE", "severity": "high", "status": "OPEN", "origin": "contradiction"}]

    def test_to_build_interim_value_waits_with_its_pending_mark(self):
        text, report = render_brief_v2(inputs(contradictions=self.contradiction, gaps=self.gaps))
        rules = place(text, "2.2")
        self.assertIn("The fee is 2 percent. [[sources § Source log - V2_PURE # F-01", rules)
        self.assertIn("⏳ PENDING (GAP-CONTRA-FEE)", rules)
        self.assertEqual(report["summary"]["divergences"], 0)
        self.assertNotIn("Defect:", text)

    def test_built_marks_the_divergence_inline_and_in_section_seven_and_nine(self):
        text, report = render_brief_v2(inputs(contradictions=self.contradiction, gaps=self.gaps,
                                              validation_direction="built"))
        self.assertIn("- ⚠ The fee is 2 percent. (`GAP-CONTRA-FEE`)", place(text, "2.2"))
        self.assertNotIn("⏳ PENDING (GAP-CONTRA-FEE)", text)
        self.assertIn("1 divergences between what is documented and what is built (⚠).", place(text, "7.2"))
        self.assertIn("| 2.2 | ⚠ | `GAP-CONTRA-FEE` |", place(text, "7.2"))
        build = place(text, "9.1")
        self.assertIn("Defect: `GAP-CONTRA-FEE`", build)
        self.assertIn("`C-01` Debt: ", build)
        self.assertEqual(report["summary"]["divergences"], 1)

    def test_unresolved_contradiction_is_only_a_pending_mark(self):
        unresolved = [{**self.contradiction[0], "resolved": False, "value": None}]
        text, _ = render_brief_v2(inputs(contradictions=unresolved, gaps=self.gaps))
        self.assertIn("⏳ PENDING (GAP-CONTRA-FEE)", place(text, "2.2"))
        self.assertNotIn("The fee is 2 percent.", text)


class TranscriptionTests(unittest.TestCase):
    raw = ("# Dashboard\n\nMetric: reduce manual preparation by up to 30 percent, TBD by finance.\n\n"
           "Users: the the operations leads.\n")

    def test_source_tbd_stays_tbd_and_keeps_the_place_pending(self):
        text, report = render_brief_v2(inputs(raw_sources=[("F-01", "raw.md", self.raw)]))
        metrics = place(text, "1.3")
        self.assertIn("reduce manual preparation by up to 30 percent, TBD by finance.", metrics)
        self.assertIn("⏳ PENDING (", metrics)
        self.assertFalse(any(p["id"] == "1.3" and p["fill"] == "covered" for p in report["places"]))

    def test_doubled_word_is_marked_sic_and_quotes_are_otherwise_verbatim(self):
        self.assertEqual(transcribe("Users: the the operations leads."), "Users: the the [sic] operations leads.")
        self.assertEqual(transcribe("It had had an effect; options A–D apply."), "It had had an effect; options A–D apply.")
        text, _ = render_brief_v2(inputs(raw_sources=[("F-01", "raw.md", self.raw)]))
        self.assertIn("the the [sic] operations leads.", text)


class WorkspaceRewriteTests(unittest.TestCase):
    def test_resolve_gaps_rewrites_only_the_answered_place(self):
        from sentinel.cli import main
        from sentinel.compilers.brief_v2 import record_brief_inferences
        from sentinel.knowledge.ledger import materialize_knowledge_ledger
        from sentinel.memory import ContextBroker
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "BRIEF_V2_REWRITE"
        old_cwd = Path.cwd()
        tmp = Path(tempfile.mkdtemp())
        os.chdir(tmp)
        out = io.StringIO()
        try:
            with patch.object(ContextBroker, "_connect_lancedb", lambda self: None), contextlib.redirect_stdout(out):
                raw = tmp / "raw.md"
                raw.write_text(scenario["raw"], encoding="utf-8")
                self.assertEqual(main(["init", pid]), 0)
                self.assertEqual(main(["ingest", pid, "--source", str(raw)]), 0)
                for index, statement in enumerate(scenario["ears"], start=1):
                    answer = tmp / f"answer-{index}.md"
                    answer.write_text(scenario["answer"].format(s=statement, i=index), encoding="utf-8")
                    self.assertEqual(main(["resolve-gaps", pid, "--source", str(answer)]), 0)
                self.assertEqual(main(["brief", pid, "--brief-version", "2", "--profile", "UI", "--genesis", "greenfield"]), 0)
                base = tmp / "workspaces" / pid
                brief = base / "02_requirements" / "project-brief.md"
                before = brief.read_text(encoding="utf-8")
                self.assertIn("⏳ PENDING (GAP-BUSINESS-RULES)", place(before, "2.2"))

                answer = tmp / "rules.md"
                answer.write_text(
                    "### GAP-BUSINESS-RULES\n- Answer: A queue with any SLA breach is high risk.\n"
                    "- Owner / source: Client workshop\n- Evidence or reference: workshop notes\n"
                    "- Decision status: confirmed\n", encoding="utf-8")
                out.truncate(0)
                out.seek(0)
                self.assertEqual(main(["resolve-gaps", pid, "--source", str(answer)]), 0)
                result = json.loads(out.getvalue())
            after = brief.read_text(encoding="utf-8")
            self.assertIn("2.2", result["brief_v2"]["rewritten_places"])
            rules = place(after, "2.2")
            self.assertIn("A queue with any SLA breach is high risk. (`GAP-BUSINESS-RULES`)", rules)
            self.assertNotIn("⏳ PENDING (GAP-BUSINESS-RULES)", rules)
            for untouched in ("1.1", "1.5", "2.1", "3.1", "4.1", "5.1"):
                with self.subTest(place=untouched):
                    self.assertEqual(place(after, untouched), place(before, untouched))
            self.assertEqual(v2_self_correction_findings(after, {"GAP-BUSINESS-RULES": {
                "statement": "A queue with any SLA breach is high risk.", "source": ""}}), [])

            # inference rows live in the ledger and survive its re-materialization
            os.chdir(tmp)
            record_brief_inferences(pid, [{"place": "4.1", "assumption": "ASM-FLOW", "statement": "One screen.",
                                           "gap": "GAP-DESIGN-FLOW"}])
            ledger = json.loads((base / "01_discovery" / "knowledge_state.json").read_text(encoding="utf-8"))
            unit = next(u for u in ledger["units"] if u["id"] == "KLU-BRIEF-001")
            self.assertEqual(unit["status"], "INFERRED")
            materialize_knowledge_ledger(pid, "", [], "", {})
            ledger = json.loads((base / "01_discovery" / "knowledge_state.json").read_text(encoding="utf-8"))
            self.assertTrue(any(u["id"] == "KLU-BRIEF-001" for u in ledger["units"]))
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
