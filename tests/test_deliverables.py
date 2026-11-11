"""IMP-272: work versus deliverable."""

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

from sentinel.deliverables import DeliverableNotReady, domain_pack_warnings, gate, pending_count, with_banner

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


class GateTests(unittest.TestCase):
    def test_pending_marks_make_a_draft_and_final_refuses(self):
        text = "# PRD\n\n- [PENDING INPUT] - resolve GAP-X.\n\n⏳ PENDING (GAP-Y)\n"
        self.assertEqual(pending_count(text), 2)
        self.assertEqual(gate(text, artifact="prd", fmt="md", final=False), {"deliverable": "draft", "pending_marks": 2})
        with self.assertRaises(DeliverableNotReady):
            gate(text, artifact="prd", fmt="md", final=True)
        self.assertEqual(gate("# PRD\n\nAll set.\n", artifact="prd", fmt="md", final=True),
                         {"deliverable": "final", "pending_marks": 0})

    def test_gap_exports_are_working_documents(self):
        text = "# Gaps\n\n[PENDING INPUT]\n"
        self.assertEqual(gate(text, artifact="gaps", fmt="md", final=True)["deliverable"], "working")
        self.assertEqual(gate(text, artifact="prd", fmt="interview", final=True)["deliverable"], "working")

    def test_banner_sits_under_the_title(self):
        stamped = with_banner("<!-- sentinel-artifact: v2 -->\n# Project Brief — X\n\nBody\n", 3, "es")
        lines = stamped.splitlines()
        self.assertEqual(lines[1], "# Project Brief — X")
        self.assertTrue(lines[3].startswith("> **BORRADOR** — quedan 3 marcas pendientes"))
        self.assertIn("**DRAFT** — 1 pending marks remain", with_banner("# T\n", 1, "en"))


class DomainPackTests(unittest.TestCase):
    def test_when_to_read_and_single_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = base / "00_raw" / "02_technology_context"
            folder.mkdir(parents=True)
            (folder / "good.md").write_text("---\nwhen_to_read: before designing the API\n---\n# API\n- Owner: Platform team\n", encoding="utf-8")
            (folder / "bad.md").write_text("# Data\n- Owner: Data team, Security\n", encoding="utf-8")
            warnings = domain_pack_warnings(base)
        self.assertEqual(len(warnings), 2)
        self.assertTrue(all("bad.md" in w for w in warnings))
        self.assertTrue(any("when_to_read" in w for w in warnings))
        self.assertTrue(any("2 owners" in w for w in warnings))

    def test_context_request_pack_declares_when_to_read_and_owner_rule(self):
        from sentinel.context_requests import render_context_request

        text = render_context_request("X", "technology", "en", Path("brief.md"), Path("gaps.md"))
        self.assertTrue(text.startswith("---\nwhen_to_read: when preparing or reviewing the technology domain context of X\n---\n"))
        self.assertIn("Every fact has a single owner", text)


class ExportTests(unittest.TestCase):
    def test_export_marks_drafts_and_final_refuses(self):
        from sentinel.cli import main
        from sentinel.export import export_artifact
        from sentinel.memory import ContextBroker
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "DELIVERABLE"
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
                self.assertEqual(main(["brief", pid]), 0)
                result = export_artifact(pid, "brief", "md")
                self.assertEqual(main(["export", pid, "--artifact", "brief", "--final"]), 1)
                gaps = export_artifact(pid, "gaps", "interview", final=True)
            self.assertEqual(result["deliverable"], "draft")
            self.assertGreater(result["pending_marks"], 0)
            exported = Path(result["path"]).read_text(encoding="utf-8")
            self.assertIn("> **DRAFT** —", exported)
            self.assertEqual(gaps["deliverable"], "working")
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
