"""IMP-191: structured digest of unstructured interactions.

Covers the invariant that matters most (seed §4 #7): the digest *proposes and
routes; it never applies*. The pure extractors are checked in isolation, then an
end-to-end pass proves the pre-filled response file cannot close a gap when
`/resolve-gaps` runs over it as-is.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.gap_resolution import CONFIRMED_STATUSES, resolve_gaps
from sentinel.interaction_digest import (
    PROPOSED_STATUS,
    asm_contradiction_signals,
    build_interaction_digest,
    decision_candidates,
    gap_answer_candidates,
    iter_citable_lines,
    render_interaction_digest,
    render_proposed_gap_response,
    significant_tokens,
)
from sentinel.sync import sync_change


class ExtractorUnitTests(unittest.TestCase):
    def test_citable_lines_are_numbered_and_stripped(self) -> None:
        lines = iter_citable_lines("first line\n\n  second line  \nthird")
        self.assertEqual(lines, [(1, "first line"), (3, "second line"), (4, "third")])

    def test_gap_answer_candidate_requires_min_overlap(self) -> None:
        gaps = [{"id": "GAP-X", "description": "authentication timeout retry policy limit"}]
        lines = [
            (1, "We set the authentication timeout retry policy to five attempts."),
            (2, "Unrelated chit chat about lunch."),
        ]
        cands = gap_answer_candidates(gaps, lines)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["gap_id"], "GAP-X")
        self.assertEqual(cands[0]["line"], 1)
        # The quote is verbatim, never synthesized.
        self.assertEqual(cands[0]["quote"], "We set the authentication timeout retry policy to five attempts.")

    def test_gap_answer_candidate_dropped_below_threshold(self) -> None:
        gaps = [{"id": "GAP-X", "description": "authentication timeout retry policy"}]
        lines = [(1, "authentication is nice")]  # only one significant token overlaps
        self.assertEqual(gap_answer_candidates(gaps, lines), [])

    def test_decision_candidates_quote_verbatim_with_cue(self) -> None:
        lines = [
            (1, "María: we decided to use Postgres for the ledger."),
            (2, "Just a normal status update line."),
            (3, "Definimos que el SLA es de 24 horas."),
        ]
        found = decision_candidates(lines)
        self.assertEqual([d["line"] for d in found], [1, 3])
        self.assertEqual(found[0]["quote"], "María: we decided to use Postgres for the ledger.")

    def test_asm_signals_reuse_metabolism_never_redetect(self) -> None:
        metabolism = {
            "invalidated_assumptions": ["ASM-QUEUE"],
            "associative_findings": [{"target": "ASM-RISK", "score": 0.4, "citation": {}}],
        }
        signals = asm_contradiction_signals(metabolism)
        self.assertEqual(signals["invalidated"], ["ASM-QUEUE"])
        self.assertEqual(signals["associative"][0]["target"], "ASM-RISK")
        # No metabolism -> empty, no crash.
        self.assertEqual(asm_contradiction_signals(None), {"invalidated": [], "associative": []})

    def test_proposed_response_uses_non_confirming_status(self) -> None:
        text = render_proposed_gap_response(
            "workspaces/X/07_changes/00_client_responses/mail.md",
            [{"gap_id": "GAP-X", "quote": "the answer verbatim", "line": 7, "overlap": 4}],
        )
        self.assertIn("### GAP-X", text)
        self.assertIn("the answer verbatim", text)
        self.assertIn(f"Decision status: {PROPOSED_STATUS}", text)
        # The whole safety of the pre-fill: PROPOSED is not a closing status.
        self.assertNotIn(PROPOSED_STATUS.lower(), CONFIRMED_STATUSES)
        self.assertIn("identify the speaker", text)

    def test_render_empty_digest_has_explicit_markers(self) -> None:
        digest = render_interaction_digest(
            "X", "CHG-1", "src.md", [], [], [], {"invalidated": [], "associative": []}, None
        )
        self.assertIn("proposes and routes; it never applies", digest)
        self.assertEqual(digest.count("- None."), 5)  # gap/decision/new-gaps/invalidated/associative
        self.assertIn("no response file written", digest)


RAW = (
    "# Billing Portal\n\n"
    "Finance users need a portal to review monthly invoices before approval. "
    "Approval must be logged for audit."
)


class DigestEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "billing.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "DIG"]), 0)
        self.assertEqual(main(["ingest", "DIG", "--source", str(self.raw)]), 0)
        self.ws = self.temp / "workspaces" / "DIG"
        gaps = [g for g in parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")) if g.get("id") != "NONE"]
        self.gap = gaps[0]

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _transcript_answering_gap(self) -> str:
        # Build a line that shares >= 3 significant tokens with the real gap
        # description, so the candidate match is deterministic regardless of the
        # default gap wording.
        tokens = sorted(significant_tokens(self.gap.get("description", "")))
        answer_line = "Ana: about " + " ".join(tokens[:4]) + " — we set it to weekly."
        return (
            "# Meeting transcript\n\n"
            f"{answer_line}\n"
            "Luis: we decided to use a nightly batch export.\n"
            "Ana: thanks everyone.\n"
        )

    def test_digest_extracts_and_routes_cited_signals(self) -> None:
        transcript = self.temp / "meeting-transcript.md"
        transcript.write_text(self._transcript_answering_gap(), encoding="utf-8")
        result = sync_change("DIG", transcript, "weekly sync", digest=True)
        digest = result["interaction_digest"]
        self.assertIsNotNone(digest)
        self.assertTrue(digest["has_signal"])
        # (a) gap answer + (b) decision candidate both surfaced.
        self.assertIn(self.gap["id"], digest["gap_answer_candidates"])
        self.assertGreaterEqual(digest["decision_candidates"], 1)

        digest_text = Path(digest["digest_path"]).read_text(encoding="utf-8")
        self.assertIn("proposes and routes; it never applies", digest_text)
        self.assertIn("we decided to use a nightly batch export", digest_text)
        self.assertIn(self.gap["id"], digest_text)

    def test_proposed_file_cannot_close_a_gap(self) -> None:
        transcript = self.temp / "mail-thread.md"
        transcript.write_text(self._transcript_answering_gap(), encoding="utf-8")
        result = sync_change("DIG", transcript, "mail", digest=True)
        proposed = result["interaction_digest"]["proposed_response_path"]
        self.assertIsNotNone(proposed)

        # Feed the untouched pre-filled file straight into /resolve-gaps.
        resolution = resolve_gaps("DIG", Path(proposed))
        # The digest proposes; it never applies. A PROPOSED status must not close.
        self.assertNotIn(self.gap["id"], resolution["closed"])

    def test_empty_interaction_still_writes_explicit_digest(self) -> None:
        neutral = self.temp / "neutral-note.md"
        neutral.write_text("# Note\n\nThanks for the update, talk soon.\n", encoding="utf-8")
        result = sync_change("DIG", neutral, "fyi", digest=True)
        digest = result["interaction_digest"]
        self.assertIsNotNone(digest)
        # No proposed response file when there are no gap-answer candidates.
        self.assertIsNone(digest["proposed_response_path"])
        self.assertTrue(Path(digest["digest_path"]).exists())

    def test_digest_off_by_default(self) -> None:
        change = self.temp / "plain-change.md"
        change.write_text("# Change\n\nWe decided to use Postgres.\n", encoding="utf-8")
        result = sync_change("DIG", change, "no digest")
        self.assertIsNone(result["interaction_digest"])


if __name__ == "__main__":
    unittest.main()
