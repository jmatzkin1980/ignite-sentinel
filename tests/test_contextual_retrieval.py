"""IMP-122 — Contextual Retrieval adapted to lenses.

A deterministic, local situational prefix (document + section + domain + iteration + RU)
is prepended to each chunk *only* for embedding and full-text indexing. The verbatim chunk
content and the read_plan anchors that the agent reads must stay unchanged.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.memory import (
    CHUNKING_VERSION,
    ContextBroker,
    build_context_prefix,
    contextualize_chunk_text,
)

ROOT = Path(__file__).parent
FIXTURE = ROOT / "fixtures" / "evals" / "support-dashboard" / "requirement.md"


class ContextPrefixUnitTests(unittest.TestCase):
    def test_chunking_version_bumped_to_v2(self) -> None:
        # Guards the intentional bump so /reindex re-chunks existing workspaces.
        self.assertEqual(CHUNKING_VERSION, "heading-table:v2")

    def test_prefix_is_deterministic_and_includes_situational_metadata(self) -> None:
        kwargs = dict(
            title="requirement",
            artifact_type="requirements",
            domain="business",
            iteration=2,
            section_path="Discovery Gaps > GAP-METRIC-SOURCE - Metric Source",
            trace_ids=["REQ-001", "RU-003", "RU-001"],
        )
        first = build_context_prefix(**kwargs)
        second = build_context_prefix(**kwargs)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("["))
        self.assertIn("document: requirement", first)
        self.assertIn("type: requirements", first)
        self.assertIn("section: Discovery Gaps > GAP-METRIC-SOURCE - Metric Source", first)
        self.assertIn("domain: business", first)
        self.assertIn("iteration: 2", first)
        # RU ids are sorted and de-duplicated, drawn from trace ids.
        self.assertIn("units: RU-001, RU-003", first)

    def test_prefix_extracts_units_from_section_path(self) -> None:
        prefix = build_context_prefix(section_path="Unit RU-007 detail", trace_ids=[])
        self.assertIn("units: RU-007", prefix)

    def test_contextualize_keeps_text_when_prefix_empty(self) -> None:
        self.assertEqual(contextualize_chunk_text("", "body"), "body")
        self.assertEqual(contextualize_chunk_text("[p]", "body"), "[p]\nbody")


class ContextualIndexingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _ingest(self, project_id: str = "CTX") -> ContextBroker:
        self.assertEqual(main(["init", project_id]), 0)
        self.assertEqual(main(["ingest", project_id, "--source", str(FIXTURE)]), 0)
        return ContextBroker(project_id)

    def test_chunk_carries_context_text_separate_from_cited_content(self) -> None:
        broker = self._ingest()
        chunks = broker.data["chunks"]
        self.assertTrue(chunks)
        for chunk in chunks:
            self.assertIn("context_text", chunk)
            self.assertTrue(chunk["context_text"].startswith("["))
            self.assertIn("document:", chunk["context_text"])
            # The verbatim content is unchanged: prefix lives only in context_text.
            self.assertEqual(chunk["text"], chunk["content"])
            self.assertNotIn("document:", chunk["text"])
            self.assertTrue(chunk["context_text"].endswith(chunk["text"]))
            self.assertTrue(chunk.get("embedding"))

    def test_retrieve_returns_verbatim_chunk_without_leaking_prefix(self) -> None:
        broker = self._ingest()
        results = broker.retrieve("success metric and target users of the dashboard", "specs")
        self.assertTrue(results)
        for row in results:
            self.assertNotIn("context_text", row)
            self.assertNotIn("embedding", row)
            self.assertFalse(row["text"].startswith("[document:"))
            self.assertNotIn("[document:", row["text"])
            self.assertIn("read_plan", row)
            self.assertEqual(row["read_plan"]["section_path"], row.get("section_path", ""))

    def test_reindex_detects_chunking_version_change(self) -> None:
        broker = self._ingest()
        artifact = broker.data["artifacts"][0]
        artifact_id = artifact["artifact_id"]
        source_hash = artifact["source_hash"]
        # Current index matches the active chunking version.
        self.assertTrue(broker.artifact_is_current(artifact_id, source_hash))
        # An index produced by the previous chunking version is considered stale,
        # so incremental /reindex will re-chunk it.
        artifact["chunking_version"] = "heading-table:v1"
        self.assertFalse(broker.artifact_is_current(artifact_id, source_hash))


if __name__ == "__main__":
    unittest.main()
