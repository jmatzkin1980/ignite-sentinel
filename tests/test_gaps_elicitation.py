"""IMP-257: gaps as elicitation — kind, closure vocabulary and citation, partial
closures, reopening, topic dedup, meanwhile and rounds."""

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

from sentinel.gap_resolution import apply_gap_responses
from sentinel.gaps import gap_kind, merge_gaps_by_topic, parse_gap_responses, parse_gap_table

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

OLD_ROW = "| GAP-USERS | business | high | OPEN | `REQ-001` | Users unclear. | Who uses it? | Source. | N/A | checklist | N/A | N/A |"
NEW_ROW = ("| GAP-USERS | business | high | CLOSED | `REQ-001` | Users unclear. | Who uses it? | Source. | N/A | checklist "
           "| N/A | N/A | client | answered |")


def gap(**over):
    base = {"id": "GAP-USERS", "lens": "business", "severity": "high", "status": "OPEN", "description": "Users unclear.",
            "question": "Who uses it?"}
    base.update(over)
    return base


def respond(gap_id="GAP-USERS", answer="Operations leads and analysts.", evidence="Workshop notes",
            decision="confirmed", closure=""):
    lines = [f"### {gap_id}", f"- Answer: {answer}", "- Owner / source: Product owner",
             f"- Evidence or reference: {evidence}", f"- Decision status: {decision}"]
    if closure:
        lines.append(f"- Closure reason: {closure}")
    return parse_gap_responses("\n".join(lines) + "\n")


class TableTests(unittest.TestCase):
    def test_old_tables_still_read_and_new_columns_are_optional(self):
        old = parse_gap_table(OLD_ROW)[0]
        self.assertNotIn("kind", old)
        self.assertNotIn("closure_reason", old)
        new = parse_gap_table(NEW_ROW)[0]
        self.assertEqual((new["kind"], new["closure_reason"]), ("client", "answered"))

    def test_kind_is_recorded_or_derived(self):
        self.assertEqual(gap_kind(gap(kind="domain")), "domain")
        self.assertEqual(gap_kind(gap(origin="contradiction")), "synthesis")
        self.assertEqual(gap_kind(gap(origin="scrutiny")), "synthesis")
        self.assertEqual(gap_kind(gap(id="GAP-BRIEF-S4")), "template")
        self.assertEqual(gap_kind(gap(severity="critical")), "client")
        self.assertEqual(gap_kind(gap(severity="low")), "domain")


class ClosureTests(unittest.TestCase):
    def apply(self, gaps, responses):
        return apply_gap_responses(gaps, responses)

    def test_confirmed_answer_with_citation_closes_as_answered(self):
        result = self.apply([gap()], respond())
        self.assertEqual(result["gaps"][0]["status"], "CLOSED")
        self.assertEqual(result["gaps"][0]["closure_reason"], "answered")
        self.assertEqual(result["findings"], [])

    def test_closure_without_citation_is_a_finding(self):
        result = self.apply([gap()], respond(evidence=""))
        self.assertEqual(len(result["findings"]), 1)
        self.assertIn("without a citation", result["findings"][0])

    def test_confirmed_tbd_is_partial(self):
        result = self.apply([gap()], respond(answer="The date is TBD by finance."))
        self.assertEqual(result["gaps"][0]["status"], "PARTIALLY_CLOSED")
        self.assertIn("confirmed-tbd", result["gaps"][0]["resolution_note"])

    def test_resolved_by_inference_stays_not_ready(self):
        result = self.apply([gap()], respond(evidence="ASM-USERS", closure="resolved_by_inference"))
        self.assertEqual(result["gaps"][0]["status"], "PARTIALLY_CLOSED")  # still blocking: NOT READY
        self.assertEqual(result["gaps"][0]["closure_reason"], "resolved_by_inference")
        self.assertEqual(result["counts"]["blocking_open"], 1)
        missing = self.apply([gap()], respond(evidence="workshop", closure="resolved_by_inference"))
        self.assertIn("must cite a ASM-* id", missing["findings"][0])

    def test_by_decision_must_cite_a_decision(self):
        result = self.apply([gap()], respond(evidence="workshop", closure="by_decision"))
        self.assertEqual(result["gaps"][0]["closure_reason"], "by_decision")
        self.assertIn("must cite a DEC-* id", result["findings"][0])
        ok = self.apply([gap()], respond(evidence="DEC-004", closure="by decision"))
        self.assertEqual(ok["findings"], [])

    def test_unknown_reason_falls_back_and_is_reported(self):
        result = self.apply([gap()], respond(closure="because"))
        self.assertEqual(result["gaps"][0]["closure_reason"], "answered")
        self.assertIn("unknown closure reason", result["findings"][0])

    def test_not_applicable_closes_by_removal(self):
        result = self.apply([gap()], respond(answer="No users screen in this release.", decision="not applicable"))
        self.assertEqual(result["gaps"][0]["closure_reason"], "by_removal")

    def test_example_data_never_closes(self):
        result = self.apply([gap()], respond(evidence="sample data from the demo"))
        self.assertEqual(result["gaps"][0]["status"], "ANSWERED")

    def test_false_premise_reopens_and_keeps_the_previous_closure(self):
        closed = gap(status="CLOSED", closure_reason="answered", resolution_note="confirmed in workshop")
        result = self.apply([closed], respond(closure="reopened_false_premise", evidence="Audit found two roles"))
        row = result["gaps"][0]
        self.assertEqual(row["status"], "OPEN")
        self.assertEqual(row["closure_reason"], "reopened_false_premise")
        self.assertIn("previous closure kept: answered: confirmed in workshop", row["resolution_note"])


class TopicDedupTests(unittest.TestCase):
    def test_a_new_gap_on_an_open_topic_extends_the_existing_row(self):
        existing = [gap(id="GAP-CTR-AAA", description="Refund approval rule for large amounts is missing",
                        question="Who approves refunds above the limit?", evidence_mention="refund limit")]
        twin = gap(id="GAP-SCRUTINY-BBB", description="Missing approval rule for large refund amounts",
                   question="Who approves refunds above the limit amount?", evidence_mention="large refunds")
        other = gap(id="GAP-SCRUTINY-CCC", description="Session timeout is not defined", question="How long is a session?")
        merged = merge_gaps_by_topic(existing, [twin, other, existing[0]])
        self.assertEqual([g["id"] for g in merged["added"]], ["GAP-SCRUTINY-CCC"])
        self.assertEqual(merged["extended"], {"GAP-SCRUTINY-BBB": "GAP-CTR-AAA"})
        self.assertEqual(merged["gaps"][0]["evidence_mention"], "refund limit; large refunds")
        self.assertIn("GAP-CTR-AAA", merged["skipped"])

    def test_closed_or_other_lens_gaps_are_not_twins(self):
        existing = [gap(id="GAP-A", status="CLOSED", description="Refund approval rule for large amounts is missing",
                        question="Who approves refunds above the limit?")]
        twin = gap(id="GAP-B", description="Refund approval rule for large amounts is missing",
                   question="Who approves refunds above the limit?")
        self.assertEqual(len(merge_gaps_by_topic(existing, [twin])["added"]), 1)
        self.assertEqual(len(merge_gaps_by_topic([dict(existing[0], status="OPEN", lens="design")], [twin])["added"]), 1)


class WorkspaceTests(unittest.TestCase):
    def test_meanwhile_rounds_and_reopening_on_invalidated_assumption(self):
        from sentinel.assumptions import update_assumption_statuses
        from sentinel.cli import main
        from sentinel.memory import ContextBroker
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "GAPS_ELICIT"
        old_cwd = Path.cwd()
        tmp = Path(tempfile.mkdtemp())
        os.chdir(tmp)
        out = io.StringIO()
        try:
            with patch.object(ContextBroker, "_connect_lancedb", lambda self: None), contextlib.redirect_stdout(out):
                raw = tmp / "raw.md"
                raw.write_text(scenario["raw"], encoding="utf-8")
                self.assertEqual(main(["init", pid, "--brief-version", "1"]), 0)
                self.assertEqual(main(["ingest", pid, "--source", str(raw)]), 0)
                assumption = tmp / "asm.json"
                assumption.write_text(json.dumps({"assumptions": [{
                    "id": "ASM-RULES", "lens": "business", "owner": "BA", "risk": "med",
                    "statement": "Any SLA breach marks the queue as high risk.",
                    "justification": "In scope: read-only risk dashboard for open queues.",
                    "closes_gap": "GAP-BUSINESS-RULES"}]}), encoding="utf-8")
                self.assertEqual(main(["assume", pid, "--source", str(assumption)]), 0)
                self.assertEqual(main(["gaps", pid]), 0)
                base = tmp / "workspaces" / pid
                gaps_md = (base / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
                self.assertIn("Meanwhile (inferred, to ratify): Any SLA breach marks the queue as high risk. (`ASM-RULES`)"
                              " — appears in brief v2 §2.2", gaps_md)
                self.assertIn("| Kind | Closure |", gaps_md)
                elicitation = json.loads((base / "01_discovery" / "gap_elicitation.json").read_text(encoding="utf-8"))
                self.assertEqual(elicitation["GAP-BUSINESS-RULES"]["meanwhile"]["assumption"], "ASM-RULES")
                self.assertIn(elicitation["GAP-BUSINESS-RULES"]["kind"], {"client", "domain"})

                out.truncate(0)
                out.seek(0)
                self.assertEqual(main(["gaps", pid, "--top", "2"]), 0)
                round_ = json.loads(out.getvalue())
                self.assertEqual(len(round_["round"]), 2)
                self.assertGreater(round_["remaining"], 0)
                lenses = [item["lens"] for item in round_["round"]]
                self.assertTrue(all(lens in {"business", "product"} for lens in lenses), lenses)
                for item in round_["round"]:
                    self.assertEqual(item["choices"][-1]["text"], "Leave pending")
                    if len(item["choices"]) > 1:
                        self.assertTrue(item["choices"][0]["recommended"])
                self.assertTrue((base / "01_discovery" / "gap_round.md").exists())

                answer = tmp / "rules.md"
                answer.write_text("### GAP-BUSINESS-RULES\n- Answer: Any SLA breach marks the queue as high risk.\n"
                                  "- Owner / source: BA\n- Evidence or reference: ASM-RULES\n"
                                  "- Decision status: confirmed\n- Closure reason: resolved_by_inference\n", encoding="utf-8")
                out.truncate(0)
                out.seek(0)
                self.assertEqual(main(["resolve-gaps", pid, "--source", str(answer)]), 0)
                self.assertEqual(json.loads(out.getvalue())["closure_findings"], [])
                rows = {g["id"]: g for g in parse_gap_table((base / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
                self.assertEqual(rows["GAP-BUSINESS-RULES"]["status"], "PARTIALLY_CLOSED")
                self.assertEqual(rows["GAP-BUSINESS-RULES"]["closure_reason"], "resolved_by_inference")

                result = update_assumption_statuses(pid, invalidated_assumption_ids={"ASM-RULES"})
            self.assertEqual(result["reopened_gaps"], ["GAP-BUSINESS-RULES"])
            rows = {g["id"]: g for g in parse_gap_table((base / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
            self.assertEqual(rows["GAP-BUSINESS-RULES"]["status"], "OPEN")
            self.assertIn("reopened: ASM-RULES invalidated", rows["GAP-BUSINESS-RULES"]["resolution_note"])
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
