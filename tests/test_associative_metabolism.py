from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.assumptions import apply_assumptions
from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.knowledge.metabolism import associative_impact_candidates
from sentinel.sync import render_associative_findings, render_impact, sync_change


class _StubStatus:
    def __init__(self, semantic: bool) -> None:
        self.semantic = semantic
        self.name = "stub"
        self.version = "v1"


class _StubBroker:
    """Mode-agnostic stand-in for ContextBroker (no real embedder / LanceDB).

    Mirrors the test_ann_candidates.py pattern: the associative step is exercised
    deterministically by controlling what retrieve() returns, independent of the
    embedder backend actually present.
    """

    def __init__(self, rows, *, semantic: bool = True, raises: bool = False) -> None:
        self.embedder_status = _StubStatus(semantic)
        self._rows = rows
        self._raises = raises
        self.calls: list[dict] = []

    def retrieve(self, query, workflow, **kwargs):
        self.calls.append({"query": query, "workflow": workflow, **kwargs})
        if self._raises:
            raise RuntimeError("retrieval boom")
        return list(self._rows)


def _chunk_row(text: str, score: float, *, chunk_id: str = "CH-1") -> dict:
    return {
        "score": score,
        "text": text,
        "content": text,
        "why_retrieved": "semantic similarity",
        "chunk_id": chunk_id,
        "trace_ids": ["DISC-1"],
        "read_plan": {
            "source_path": "workspaces/X/01_discovery/assumptions.md",
            "section_path": "Governed Assumptions",
            "line_start": 10,
            "line_end": 14,
        },
    }


class AssociativeCandidateUnitTests(unittest.TestCase):
    def test_finding_is_cited_under_semantic_embedder(self) -> None:
        broker = _StubBroker([_chunk_row("Row for ASM-RISK-TAXONOMY about queue risk.", 0.41)])
        findings = associative_impact_candidates(broker, "reworded change text", already_invalidated=set())

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["target"], "ASM-RISK-TAXONOMY")
        self.assertEqual(finding["kind"], "associative")
        self.assertEqual(finding["score"], 0.41)
        self.assertEqual(finding["why_retrieved"], "semantic similarity")
        self.assertEqual(finding["citation"]["source_path"], "workspaces/X/01_discovery/assumptions.md")
        self.assertEqual(finding["citation"]["line_start"], 10)
        # The retrieval is scoped to the governed assumption register.
        self.assertEqual(broker.calls[0]["artifact_type"], "assumption_register")

    def test_degrades_without_semantic_embedder(self) -> None:
        broker = _StubBroker([_chunk_row("ASM-RISK-TAXONOMY", 0.9)], semantic=False)
        self.assertEqual(associative_impact_candidates(broker, "text", already_invalidated=set()), [])
        # Hash-mode degradation must not even hit retrieval.
        self.assertEqual(broker.calls, [])

    def test_degrades_without_broker(self) -> None:
        self.assertEqual(associative_impact_candidates(None, "text", already_invalidated=set()), [])

    def test_retrieval_failure_degrades_without_error(self) -> None:
        broker = _StubBroker([], raises=True)
        self.assertEqual(associative_impact_candidates(broker, "text", already_invalidated=set()), [])

    def test_below_threshold_is_dropped(self) -> None:
        broker = _StubBroker([_chunk_row("ASM-RISK-TAXONOMY", 0.05)])
        self.assertEqual(associative_impact_candidates(broker, "text", already_invalidated=set()), [])

    def test_already_invalidated_is_not_echoed(self) -> None:
        broker = _StubBroker([_chunk_row("ASM-RISK-TAXONOMY contradicted", 0.5)])
        findings = associative_impact_candidates(
            broker, "text", already_invalidated={"ASM-RISK-TAXONOMY"}
        )
        self.assertEqual(findings, [])

    def test_candidate_reported_once_across_chunks(self) -> None:
        broker = _StubBroker(
            [
                _chunk_row("ASM-RISK-TAXONOMY here", 0.5, chunk_id="CH-1"),
                _chunk_row("ASM-RISK-TAXONOMY again", 0.4, chunk_id="CH-2"),
            ]
        )
        findings = associative_impact_candidates(broker, "text", already_invalidated=set())
        self.assertEqual([f["target"] for f in findings], ["ASM-RISK-TAXONOMY"])


class AssociativeRenderTests(unittest.TestCase):
    def test_render_empty_findings(self) -> None:
        self.assertEqual(render_associative_findings([]), "- None.")
        self.assertEqual(render_associative_findings(None), "- None.")

    def test_impact_report_includes_cited_associative_section(self) -> None:
        metabolism = {
            "associative_findings": [
                {
                    "target": "ASM-RISK-TAXONOMY",
                    "reason": "posible impacto por similitud semántica",
                    "score": 0.41,
                    "citation": {
                        "source_path": "workspaces/X/01_discovery/assumptions.md",
                        "section_path": "Governed Assumptions",
                        "line_start": 10,
                        "line_end": 14,
                    },
                }
            ]
        }
        report = render_impact("X", "CHG-1", [], [], "note", knowledge_metabolism=metabolism)

        self.assertIn("## Associative Impact Candidates (BA review)", report)
        self.assertIn("nothing is auto-invalidated", report)
        self.assertIn("`ASM-RISK-TAXONOMY` (sim 0.41)", report)
        self.assertIn("workspaces/X/01_discovery/assumptions.md", report)
        self.assertIn("L10-14", report)


RAW = (
    "# Operations Risk Board\n\n"
    "Support leads need a board for queue risk before the daily standup. "
    "The team currently uses the current queue risk taxonomy during manual triage."
)


class AssociativeMetabolismIntegrationTests(unittest.TestCase):
    """End-to-end: in the efficient hash mode (no semantic model) the associative
    step degrades to no findings, no error, and the assumption is never touched."""

    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "risk-board.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "ASSOC"]), 0)
        self.assertEqual(main(["ingest", "ASSOC", "--source", str(self.raw)]), 0)
        self.ws = self.temp / "workspaces" / "ASSOC"
        gaps = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        self.gap_id = next(gap["id"] for gap in gaps if gap.get("id") != "NONE")
        source = self.temp / "assumptions.json"
        source.write_text(
            json.dumps(
                {
                    "assumptions": [
                        {
                            "id": "ASM-RISK-TAXONOMY",
                            "lens": "product",
                            "statement": "The board can provisionally use the current queue risk taxonomy.",
                            "owner": "Product Lead",
                            "risk": "med",
                            "justification": "The team currently uses the current queue risk taxonomy during manual triage.",
                            "closes_gap": self.gap_id,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        apply_assumptions("ASSOC", source)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_reworded_change_degrades_in_hash_mode(self) -> None:
        change = self.temp / "reworded.md"
        # Contradicts the taxonomy assumption by meaning, but carries no
        # deterministic invalidation vocabulary.
        change.write_text(
            "The triage board will categorize queue incidents through the freshly adopted "
            "severity matrix the operations team began using this quarter.",
            encoding="utf-8",
        )
        result = sync_change("ASSOC", change, "operations update")
        metabolism = result["knowledge_metabolism"]

        # Hash mode (no semantic embedder) → deterministic behavior, no findings.
        self.assertEqual(metabolism["associative_findings"], [])
        self.assertEqual(metabolism["invalidated_assumptions"], [])
        self.assertIn("ASSUMED", (self.ws / "01_discovery" / "assumptions.md").read_text(encoding="utf-8"))
        self.assertNotIn("INVALIDATED", (self.ws / "01_discovery" / "assumptions.md").read_text(encoding="utf-8"))

        report = next((self.ws / "07_changes").rglob("*impact_report.md")).read_text(encoding="utf-8")
        self.assertIn("## Associative Impact Candidates (BA review)", report)


if __name__ == "__main__":
    unittest.main()
