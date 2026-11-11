"""IMP-258b: agentic anchor review (/scrutinize --mode anchors)."""

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

from sentinel.anchor_review import AnchorReviewError, validate_reviews

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))


class EvalTests(unittest.TestCase):
    def test_every_seeded_case_matches(self):
        import run_anchor_review_evals

        result = run_anchor_review_evals.run()
        self.assertGreaterEqual(len(result["cases"]), 8)
        self.assertEqual({c["split"] for c in result["cases"]}, {"tuning", "held_out"})
        for case in result["cases"]:
            with self.subTest(case=case["case"]):
                self.assertTrue(case["ok"], case)

    def test_v1_brief_is_refused(self):
        with self.assertRaises(AnchorReviewError):
            validate_reviews("# Brief\n\n## 1. Identity\n\n- x\n", {}, {"anchors": [{"verdict": "holds"}]})


class WorkspaceTests(unittest.TestCase):
    def test_review_opens_a_gap_and_never_touches_the_brief(self):
        from sentinel.cli import main
        from sentinel.gaps import parse_gap_table
        from sentinel.memory import ContextBroker
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "ANCHORREVIEW"
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
                self.assertEqual(main(["brief", pid, "--profile", "UI", "--genesis", "greenfield"]), 0)
                base = tmp / "workspaces" / pid
                brief = base / "02_requirements" / "project-brief.md"
                before = brief.read_text(encoding="utf-8")
                payload = tmp / "review.json"
                payload.write_text(json.dumps({"anchors": [
                    {"place": "1.1", "source": "F-01",
                     "claim": "Objective: let operations leads review risk queues before the daily meeting.",
                     "source_quote": "let operations leads review risk queues before the daily meeting", "verdict": "holds"},
                    {"place": "1.3", "source": "F-01",
                     "claim": "Metric: reduce manual preparation by 30 percent in the first release month.",
                     "source_quote": "reduce manual preparation by 30 percent in the first release month", "verdict": "says_less",
                     "inverted": "A 30 percent reduction is a goal; the source gives no baseline or measurement",
                     "question": "What is the baseline and how is preparation time measured?"},
                ]}), encoding="utf-8")
                out.truncate(0); out.seek(0)
                self.assertEqual(main(["scrutinize", pid, "--mode", "anchors", "--source", str(payload)]), 0)
                result = json.loads(out.getvalue())
            self.assertEqual(result["counts"], {"holds": 1, "says_less": 1, "says_opposite": 0})
            self.assertEqual(result["rejected"], [])
            gap_id = result["gaps_opened"][0]
            self.assertTrue(gap_id.startswith("GAP-ANC-"))
            rows = {g["id"]: g for g in parse_gap_table((base / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
            self.assertEqual(rows[gap_id]["origin"], "anchor-review")
            self.assertEqual(brief.read_text(encoding="utf-8"), before)
            self.assertIn("holds 1", (base / "01_discovery" / "anchor_review_log.md").read_text(encoding="utf-8"))
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
