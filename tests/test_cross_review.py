"""IMP-260b: semantic crosses of the brief v2 (/self-review --crosses)."""

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

from sentinel.cross_review import CrossReviewError, rules, validate_crosses

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))


class EvalTests(unittest.TestCase):
    def test_every_seeded_case_matches(self):
        import run_cross_review_evals

        result = run_cross_review_evals.run()
        self.assertGreaterEqual(len(result["cases"]), 8)
        self.assertEqual({c["split"] for c in result["cases"]}, {"tuning", "held_out"})
        for case in result["cases"]:
            with self.subTest(case=case["case"]):
                self.assertTrue(case["ok"], case)

    def test_catalog_and_v1(self):
        catalog = rules()
        self.assertEqual(len(catalog), 10)
        for rule_id in ("cross_a_scope_lenses", "cross_b_business_product", "cross_c_product_design", "cross_d_design_technical",
                        "field_has_origin", "endpoint_in_service", "retention_has_job", "obligation_has_control",
                        "existing_system_is_stated", "story_criterion_item"):
            self.assertIn(rule_id, catalog)
        with self.assertRaises(CrossReviewError):
            validate_crosses("# Brief\n\n## 1. Identity\n\n- x\n", {"crosses": [{"rule": "x"}]})


class WorkspaceTests(unittest.TestCase):
    def test_cross_review_opens_a_gap(self):
        from sentinel.cli import main
        from sentinel.gaps import parse_gap_table
        from sentinel.memory import ContextBroker
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "CROSSREVIEW"
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
                before = (base / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
                payload = tmp / "crosses.json"
                payload.write_text(json.dumps({"crosses": [{
                    "rule": "cross_a_scope_lenses", "kind": "missing",
                    "a": {"place": "6.1", "quote": "read-only risk dashboard for open queues"},
                    "missing_in": "4.1", "finding": "the in-scope dashboard has no screen in 4.1",
                    "question": "Which screen shows the open queues?"}]}), encoding="utf-8")
                out.truncate(0); out.seek(0)
                self.assertEqual(main(["self-review", pid, "--crosses", "--source", str(payload)]), 0)
                result = json.loads(out.getvalue())
            self.assertEqual(result["counts"], {"conflict": 0, "missing": 1})
            gap_id = result["gaps_opened"][0]
            self.assertTrue(gap_id.startswith("GAP-XRV-"))
            rows = {g["id"]: g for g in parse_gap_table((base / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
            self.assertEqual(rows[gap_id]["origin"], "cross-review")
            self.assertEqual((base / "02_requirements" / "project-brief.md").read_text(encoding="utf-8"), before)
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
