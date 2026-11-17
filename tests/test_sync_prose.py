"""IMP-337: /sync with a late change written in prose.

H1 (review 2026-11-16): a note reversing confirmed scope went through /sync and
nothing moved — no contradiction, no reopened gap, no invalidated assumption —
while the skill claimed closed gaps "are reopened". The fix, in three steps:

- 337a (deterministic): /sync says how much of the note it stored without
  interpreting (`prose_review`), widens the decision cue ("The board decided:"),
  and lists, as a non-applying hint, the closed gaps and live assumptions that
  share significant tokens with each decision line. Nothing moves from prose.
- 337b: `/sync --source NOTE --analysis FILE`. An agent proposes change
  candidates with two verbatim quotes (note and target); the runtime validates
  both and opens one blocking `GAP-CHG-<hash>` per valid candidate, or refuses
  the whole file (exit 3) listing every reason.
- 337c: the BA confirms with `/gaps --id GAP-CHG-x --disposition accepted|rejected`.
  `accepted` reopens the target gap or invalidates the assumption; `rejected`
  closes the GAP-CHG as a false alarm.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from sentinel.assumptions import load_assumptions
from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.interaction_digest import decision_candidates, iter_citable_lines

PID = "PROSE"
RAW = (
    "# Late Fee Portal\n\n"
    "We need a customer portal for the collections team. The objective is to "
    "reduce manual work. Data is stored in the legacy billing system.\n"
)
SCOPE_ANSWER = "Charging a late fee online is out of scope for the first version."
NOTE = (
    "# Board meeting, 12 November\n\n"
    "The board decided: charging a late fee online is part of the first version.\n"
    "Attendees reviewed the quarterly roadmap without further comments.\n"
)
NOTE_QUOTE = "charging a late fee online is part of the first version"
ASM_STATEMENT = "Customer records come from the legacy billing system."


def run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class DecisionCueTests(unittest.TestCase):
    def cues(self, text: str) -> list[str]:
        return [item["quote"] for item in decision_candidates(iter_citable_lines(text))]

    def test_third_person_decisions_are_caught_in_english(self) -> None:
        for line in (
            "The board decided: charging a late fee online is part of the first version.",
            "Finance approved: refunds stay manual.",
            "The steering committee has decided that exports are CSV only.",
            "Legal resolved: receipts keep the tax id.",
        ):
            self.assertEqual(self.cues(line), [line], line)

    def test_third_person_decisions_are_caught_in_spanish(self) -> None:
        for line in (
            "El directorio decidió: el cobro de mora en línea entra en la primera versión.",
            "Se resolvió que los reembolsos siguen siendo manuales.",
            "Finanzas aprobó: la exportación es solo CSV.",
        ):
            self.assertEqual(self.cues(line), [line], line)

    def test_plain_prose_is_not_a_decision(self) -> None:
        self.assertEqual(self.cues("Attendees reviewed the quarterly roadmap without further comments."), [])


class SyncProseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        (self.temp / "raw.md").write_text(RAW, encoding="utf-8")
        self.assertEqual(run(["init", PID, "--brief-version", "1"])[0], 0)
        self.assertEqual(run(["ingest", PID, "--source", str(self.temp / "raw.md")])[0], 0)
        self.ws = self.temp / "workspaces" / PID
        rows = self.gaps()
        self.assertGreaterEqual(len(rows), 2)
        self.scope_gap = rows[0]["id"]
        self.held_gap = rows[1]["id"]
        answers = self.temp / "client-answers.md"
        answers.write_text(
            f"### {self.scope_gap}\n\n- Answer: {SCOPE_ANSWER}\n- Owner / source: Product owner\n"
            "- Evidence or reference: kickoff notes\n- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(run(["resolve-gaps", PID, "--source", str(answers)])[0], 0)
        self.assertEqual(self.gap(self.scope_gap)["status"], "CLOSED")
        assumption = self.temp / "assumptions.json"
        assumption.write_text(json.dumps({"assumptions": [{
            "id": "ASM-001", "lens": "product", "statement": ASM_STATEMENT, "owner": "BA",
            "risk": "low", "justification": "Data is stored in the legacy billing system.",
            "closes_gap": self.held_gap,
        }]}), encoding="utf-8")
        self.assertEqual(run(["assume", PID, "--source", str(assumption)])[0], 0)
        self.note = self.temp / "board-meeting-notes.md"
        self.note.write_text(NOTE, encoding="utf-8")

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    # helpers -------------------------------------------------------------------

    def gaps(self) -> list[dict[str, str]]:
        text = (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        return [gap for gap in parse_gap_rows(text) if gap.get("id") != "NONE"]

    def gap(self, gap_id: str) -> dict[str, str]:
        return next(gap for gap in self.gaps() if gap["id"] == gap_id)

    def change_gaps(self) -> list[dict[str, str]]:
        return [gap for gap in self.gaps() if gap["id"].startswith("GAP-CHG-")]

    def asm_status(self) -> str:
        return next(row for row in load_assumptions(PID) if row["id"] == "ASM-001")["status"]

    def analysis(self, candidates: list[dict[str, str]]) -> Path:
        path = self.temp / "change-analysis.json"
        path.write_text(json.dumps({"candidates": candidates}), encoding="utf-8")
        return path

    def reopen_candidate(self) -> dict[str, str]:
        return {"kind": "reopen_gap", "target": self.scope_gap, "note_quote": NOTE_QUOTE,
                "target_quote": "out of scope for the first version"}

    def invalidate_candidate(self) -> dict[str, str]:
        return {"kind": "invalidate_assumption", "target": "ASM-001", "note_quote": NOTE_QUOTE,
                "target_quote": "come from the legacy billing system"}

    def sync_with(self, candidates: list[dict[str, str]]) -> dict:
        code, out, err = run(["sync", PID, "--source", str(self.note), "--analysis", str(self.analysis(candidates))])
        self.assertEqual(code, 0, err)
        return json.loads(out)

    # 337a ----------------------------------------------------------------------

    def test_prose_note_reports_what_was_not_interpreted_and_hints_the_closed_gap(self) -> None:
        assumptions_before = (self.ws / "01_discovery" / "assumptions.md").read_bytes()
        code, out, err = run(["sync", PID, "--source", str(self.note)])
        self.assertEqual(code, 0, err)
        review = json.loads(out)["prose_review"]
        self.assertGreater(review["uninterpreted_lines"], 0)
        self.assertTrue(review["notice"])
        self.assertEqual(review["decision_candidates"], 1)
        hint = review["hints"][0]
        self.assertIn(NOTE_QUOTE, hint["quote"])
        self.assertIn(self.scope_gap, [item["id"] for item in hint["related_gaps"]])
        self.assertIn("nothing was applied", hint["notice"])
        # Nothing moved from prose alone.
        self.assertEqual(self.gap(self.scope_gap)["status"], "CLOSED")
        self.assertEqual(self.change_gaps(), [])
        self.assertEqual((self.ws / "01_discovery" / "assumptions.md").read_bytes(), assumptions_before)

    def test_structured_answers_only_leave_nothing_uninterpreted(self) -> None:
        answers = self.temp / "answers-only.md"
        answers.write_text(
            f"### {self.held_gap}\n\n- Answer: The collections lead owns the data.\n"
            "- Owner / source: Collections lead\n- Evidence or reference: mail\n- Decision status: pending\n",
            encoding="utf-8",
        )
        code, out, err = run(["sync", PID, "--source", str(answers)])
        self.assertEqual(code, 0, err)
        review = json.loads(out)["prose_review"]
        self.assertEqual(review["uninterpreted_lines"], 0)
        self.assertEqual(review["notice"], "")

    def test_digest_lists_the_hint_in_its_own_section(self) -> None:
        code, out, err = run(["sync", PID, "--source", str(self.note), "--digest"])
        self.assertEqual(code, 0, err)
        digest = Path(json.loads(out)["interaction_digest"]["digest_path"]).read_text(encoding="utf-8")
        self.assertIn("(f) Possible Changes To What Was Confirmed", digest)
        self.assertIn(self.scope_gap, digest.split("(f) Possible Changes")[1])

    # 337b ----------------------------------------------------------------------

    def test_analysis_with_valid_quotes_opens_one_blocking_change_gap_per_candidate(self) -> None:
        result = self.sync_with([self.reopen_candidate(), self.invalidate_candidate()])
        opened = result["change_analysis"]["opened"]
        self.assertEqual(len(opened), 2)
        rows = {gap["id"]: gap for gap in self.change_gaps()}
        self.assertEqual(sorted(rows), sorted(opened))
        for gap in rows.values():
            self.assertEqual(gap["severity"], "high")
            self.assertEqual(gap["status"], "OPEN")
            self.assertEqual(gap["origin"], "agent")
        reopen = next(gap for gap in rows.values() if self.scope_gap in gap["description"])
        self.assertIn(NOTE_QUOTE, reopen["description"])
        self.assertIn("out of scope for the first version", reopen["description"])
        # Nothing else moves yet.
        self.assertEqual(self.gap(self.scope_gap)["status"], "CLOSED")
        self.assertEqual(self.asm_status(), "ASSUMED")

    def test_same_candidate_twice_does_not_duplicate(self) -> None:
        self.sync_with([self.reopen_candidate()])
        second = self.sync_with([self.reopen_candidate()])
        self.assertEqual(second["change_analysis"]["opened"], [])
        self.assertEqual(len(self.change_gaps()), 1)

    def test_fabricated_quotes_refuse_the_whole_file_and_write_nothing(self) -> None:
        gaps_before = (self.ws / "01_discovery" / "gaps.md").read_bytes()
        assumptions_before = (self.ws / "01_discovery" / "assumptions.md").read_bytes()
        changes_before = sorted(p.as_posix() for p in (self.ws / "07_changes").rglob("*") if p.is_file())
        bad_note = {**self.reopen_candidate(), "note_quote": "The board approved a refund flow"}
        bad_target = {**self.invalidate_candidate(), "target_quote": "records are typed by hand"}
        code, out, err = run(["sync", PID, "--source", str(self.note),
                              "--analysis", str(self.analysis([bad_note, bad_target]))])
        self.assertEqual(code, 3)
        self.assertIn(self.scope_gap, err)
        self.assertIn("ASM-001", err)
        self.assertEqual((self.ws / "01_discovery" / "gaps.md").read_bytes(), gaps_before)
        self.assertEqual((self.ws / "01_discovery" / "assumptions.md").read_bytes(), assumptions_before)
        self.assertEqual(sorted(p.as_posix() for p in (self.ws / "07_changes").rglob("*") if p.is_file()),
                         changes_before)

    def test_target_in_the_wrong_state_is_refused(self) -> None:
        wrong = {**self.reopen_candidate(), "target": self.held_gap}  # still open
        code, _, err = run(["sync", PID, "--source", str(self.note), "--analysis", str(self.analysis([wrong]))])
        self.assertEqual(code, 3)
        self.assertIn(self.held_gap, err)

    def test_analysis_needs_source(self) -> None:
        code, _, err = run(["sync", PID, "--analysis", str(self.analysis([self.reopen_candidate()]))])
        self.assertEqual(code, 3)
        self.assertIn("--source", err)

    def test_next_names_the_blocking_change_gap(self) -> None:
        opened = self.sync_with([self.reopen_candidate()])["change_analysis"]["opened"]
        code, out, err = run(["next", PID])
        self.assertEqual(code, 0, err)
        step = json.loads(out)
        text = json.dumps(step)
        self.assertIn(opened[0], text)
        self.assertIn("--disposition", text)

    # 337c ----------------------------------------------------------------------

    def test_accepted_reopens_the_target_gap(self) -> None:
        chg = self.sync_with([self.reopen_candidate()])["change_analysis"]["opened"][0]
        code, out, err = run(["gaps", PID, "--id", chg, "--disposition", "accepted"])
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["applied"]["reopened_gaps"], [self.scope_gap])
        self.assertIn("knowledge_metabolism", result["applied"])
        target = self.gap(self.scope_gap)
        self.assertEqual(target["status"], "OPEN")
        self.assertIn("previous closure kept", target["resolution_note"])
        self.assertIn(chg, target["resolution_note"])
        self.assertEqual(self.gap(chg)["status"], "CLOSED")

    def test_accepted_invalidates_the_assumption(self) -> None:
        chg = self.sync_with([self.invalidate_candidate()])["change_analysis"]["opened"][0]
        code, out, err = run(["gaps", PID, "--id", chg, "--disposition", "accepted"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["applied"]["invalidated_assumptions"], ["ASM-001"])
        self.assertEqual(self.asm_status(), "INVALIDATED")
        self.assertEqual(self.gap(chg)["status"], "CLOSED")

    def test_rejected_closes_it_as_a_false_alarm(self) -> None:
        chg = self.sync_with([self.reopen_candidate()])["change_analysis"]["opened"][0]
        code, out, err = run(["gaps", PID, "--id", chg, "--disposition", "rejected",
                              "--reason", "The board note restates an older draft."])
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["channels"]["agent"]["rejected"], 1)
        closed = self.gap(chg)
        self.assertEqual(closed["status"], "CLOSED")
        self.assertIn("false alarm", closed["resolution_note"])
        self.assertEqual(self.gap(self.scope_gap)["status"], "CLOSED")
        self.assertEqual(self.asm_status(), "ASSUMED")

    def test_a_disposed_change_gap_cannot_be_applied_twice(self) -> None:
        chg = self.sync_with([self.reopen_candidate()])["change_analysis"]["opened"][0]
        self.assertEqual(run(["gaps", PID, "--id", chg, "--disposition", "accepted"])[0], 0)
        code, _, err = run(["gaps", PID, "--id", chg, "--disposition", "accepted"])
        self.assertEqual(code, 3)
        self.assertIn("already", err)


if __name__ == "__main__":
    unittest.main()
