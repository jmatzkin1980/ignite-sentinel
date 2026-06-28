"""IMP-126 — Episodic/temporal tier with recency.

A read-only timeline of "what changed and when" derived from the chunks already
indexed for changes, their impact/metabolism trail, and interactions, plus an
optional recency-first ordering on retrieve. Both work without LanceDB or a
semantic model (deterministic hash mode), reuse iteration/timestamps, and never
persist new state or duplicate the graph.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.memory import ContextBroker


class ChangeTimelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "TL"]), 0)
        self.broker = ContextBroker("TL")

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _index(self, artifact_id: str, artifact_type: str, iteration: int, text: str = "body text") -> None:
        self.broker.index_artifact(
            artifact_id,
            artifact_type,
            Path(f"07_changes/{artifact_id}.md"),
            text,
            trace_ids=[artifact_id],
            iteration=iteration,
        )

    def test_timeline_lists_episodic_events_newest_first(self) -> None:
        self._index("CHG-001", "change", iteration=1, text="first change")
        self._index("DEC-001", "impact_report", iteration=1, text="impact of first change")
        self._index("CHG-002", "change", iteration=2, text="second change")
        # A non-episodic artifact must never appear in the timeline.
        self._index("REQ-001", "requirement", iteration=3, text="a requirement")

        timeline = self.broker.build_change_timeline()
        ids = [event["artifact_id"] for event in timeline["events"]]

        self.assertEqual(timeline["count"], 3)
        self.assertNotIn("REQ-001", ids)
        # Newest iteration first; same-iteration events keep deterministic order.
        self.assertEqual(ids[0], "CHG-002")
        self.assertIn("CHG-001", ids)
        self.assertIn("DEC-001", ids)
        first = timeline["events"][0]
        self.assertEqual(first["artifact_type"], "change")
        self.assertTrue(first["indexed_at"])
        self.assertEqual(first["trace_ids"], ["CHG-002"])
        self.assertIn("source_path", first)

    def test_timeline_filters_by_artifact_type_and_trace_id(self) -> None:
        self._index("CHG-001", "change", iteration=1)
        self._index("DEC-001", "impact_report", iteration=2)

        only_changes = self.broker.build_change_timeline(artifact_type="change")
        self.assertEqual([e["artifact_id"] for e in only_changes["events"]], ["CHG-001"])

        only_trace = self.broker.build_change_timeline(trace_id="DEC-001")
        self.assertEqual([e["artifact_id"] for e in only_trace["events"]], ["DEC-001"])

    def test_timeline_respects_limit(self) -> None:
        for index in range(4):
            self._index(f"CHG-{index:03d}", "change", iteration=index + 1)
        timeline = self.broker.build_change_timeline(limit=2)
        self.assertEqual(timeline["count"], 2)
        self.assertEqual([e["artifact_id"] for e in timeline["events"]], ["CHG-003", "CHG-002"])

    def test_timeline_is_read_only_and_persists_no_pack(self) -> None:
        self._index("CHG-001", "change", iteration=1)
        packs_dir = Path("workspaces") / "TL" / "08_context_packs"
        before = set(packs_dir.glob("*.json")) if packs_dir.exists() else set()
        timeline = self.broker.build_change_timeline()
        after = set(packs_dir.glob("*.json")) if packs_dir.exists() else set()
        # The timeline derives from the SSoT; unlike build_context_pack it neither
        # writes a pack file nor reports a persisted path.
        self.assertEqual(before, after)
        self.assertNotIn("path", timeline)


class RetrieveRecencyOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "ORD"]), 0)
        self.broker = ContextBroker("ORD")
        # Older artifact is the strong lexical match; newer one is a weaker match.
        self.broker.index_artifact(
            "CHG-OLD",
            "change",
            Path("07_changes/old.md"),
            "alpha beta gamma delta epsilon",
            trace_ids=["CHG-OLD"],
            iteration=1,
        )
        self.broker.index_artifact(
            "CHG-NEW",
            "change",
            Path("07_changes/new.md"),
            "alpha unrelated wording here",
            trace_ids=["CHG-NEW"],
            iteration=2,
        )

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_relevance_order_keeps_strong_match_first(self) -> None:
        results = self.broker.retrieve("alpha beta gamma delta epsilon", "sync")
        self.assertEqual(results[0]["artifact_id"], "CHG-OLD")

    def test_recency_order_promotes_newest(self) -> None:
        results = self.broker.retrieve("alpha beta gamma delta epsilon", "sync", order="recency")
        self.assertEqual(results[0]["artifact_id"], "CHG-NEW")
        # Both candidates are still present; only their order changed.
        self.assertEqual(
            {row["artifact_id"] for row in results},
            {"CHG-OLD", "CHG-NEW"},
        )


if __name__ == "__main__":
    unittest.main()
