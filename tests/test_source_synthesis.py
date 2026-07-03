import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.core.state import read_state


class SourceSynthesisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp)

    def write_source(self, name: str, text: str) -> Path:
        path = self.temp / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_single_ingest_writes_source_synthesis_without_changing_core_contract(self):
        source = self.write_source(
            "single.md",
            "Need a read-only dashboard for support leads. Acceptance: leads see queue risk before standup.",
        )

        self.assertEqual(main(["init", "SYNTH"]), 0)
        self.assertEqual(main(["ingest", "SYNTH", "--source", str(source)]), 0)

        workspace = self.temp / "workspaces" / "SYNTH"
        synthesis = workspace / "01_discovery" / "source_synthesis.md"
        requirements = workspace / "02_requirements" / "requirements.md"
        gaps = workspace / "01_discovery" / "gaps.md"
        state = read_state("SYNTH")

        self.assertTrue(synthesis.exists())
        self.assertTrue(requirements.exists())
        self.assertTrue(gaps.exists())
        self.assertIn("source_synthesis", state["artifacts"])
        self.assertIn("00_raw/single.md", synthesis.read_text(encoding="utf-8"))

    def test_two_ingests_preserve_divergent_source_citations_separately(self):
        first = self.write_source(
            "ops.md",
            "Need a dashboard for support leads. Metric source is the ticket queue and baseline is last month.",
        )
        second = self.write_source(
            "finance.md",
            "Need a dashboard for finance reviewers. Metric source is the billing queue and baseline is last quarter.",
        )

        self.assertEqual(main(["init", "DIVERGE"]), 0)
        self.assertEqual(main(["ingest", "DIVERGE", "--source", str(first)]), 0)
        self.assertEqual(main(["ingest", "DIVERGE", "--source", str(second)]), 0)

        synthesis = (
            self.temp
            / "workspaces"
            / "DIVERGE"
            / "01_discovery"
            / "source_synthesis.md"
        ).read_text(encoding="utf-8")

        self.assertIn("00_raw/ops.md", synthesis)
        self.assertIn("00_raw/finance.md", synthesis)
        self.assertIn("Metric source is the ticket queue and baseline is last month.", synthesis)
        self.assertIn("Metric source is the billing queue and baseline is last quarter.", synthesis)
        self.assertIn("| `00_raw/ops.md` |", synthesis)
        self.assertIn("| `00_raw/finance.md` |", synthesis)

    def test_source_synthesis_is_never_indexed_into_memory(self):
        # IMP-160: the synthesis is verbatim citations of already-indexed raw
        # sources; indexing it would duplicate evidence and displace the real
        # source in the retrieval shortlist. Ingest and reindex must both skip it.
        from sentinel.core.io import read_json

        source = self.write_source(
            "single.md",
            "Need a read-only dashboard for support leads. Acceptance: leads see queue risk before standup.",
        )
        self.assertEqual(main(["init", "MEM"]), 0)
        self.assertEqual(main(["ingest", "MEM", "--source", str(source)]), 0)
        self.assertEqual(main(["reindex", "MEM", "--full"]), 0)
        memory = read_json(self.temp / "workspaces" / "MEM" / "memory.json", {"chunks": []})
        synthesis_chunks = [
            chunk for chunk in memory.get("chunks", []) if chunk.get("type") == "source_synthesis"
        ]
        self.assertEqual(synthesis_chunks, [])


if __name__ == "__main__":
    unittest.main()
