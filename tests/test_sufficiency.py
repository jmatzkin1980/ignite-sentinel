"""IMP-259: sufficiency of the brief v2 (/self-review --sufficiency)."""

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

from sentinel.sufficiency import SufficiencyError, validate_obstacles

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))


class EvalTests(unittest.TestCase):
    def test_every_seeded_case_matches(self):
        import run_sufficiency_evals

        result = run_sufficiency_evals.run()
        self.assertGreaterEqual(len(result["cases"]), 8)
        self.assertEqual({c["split"] for c in result["cases"]}, {"tuning", "held_out"})
        for case in result["cases"]:
            with self.subTest(case=case["case"]):
                self.assertTrue(case["ok"], case)

    def test_v1_brief_is_refused(self):
        with self.assertRaises(SufficiencyError):
            validate_obstacles("# Brief\n\n## 1. Identity\n\n- x\n", {"obstacles": [{"place": "1", "status": "covered"}]})


class WorkspaceTests(unittest.TestCase):
    def test_rounds_open_gaps_until_only_covered(self):
        from sentinel.cli import main
        from sentinel.gaps import parse_gap_table
        from sentinel.memory import ContextBroker
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "SUFFICIENCY"
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
                payload = tmp / "round1.json"
                payload.write_text(json.dumps({"round": 1, "obstacles": [
                    {"place": "C-01", "status": "missing", "would_resolve": "Which queues are listed and in what order",
                     "question": "Which queues appear and in what order?"},
                    {"place": "1.1", "status": "covered"},
                    {"place": "1.1", "status": "missing", "would_resolve": "Users: operations leads.",
                     "question": "Who are the users?"},
                ]}), encoding="utf-8")
                out.truncate(0); out.seek(0)
                self.assertEqual(main(["self-review", pid, "--sufficiency", "--source", str(payload)]), 0)
                first = json.loads(out.getvalue())
                done = tmp / "round2.json"
                done.write_text(json.dumps({"round": 2, "obstacles": [{"place": "1.1", "status": "covered"},
                                                                      {"place": "C-01", "status": "covered"}]}), encoding="utf-8")
                out.truncate(0); out.seek(0)
                self.assertEqual(main(["self-review", pid, "--sufficiency", "--source", str(done)]), 0)
                second = json.loads(out.getvalue())
                gap_id = first["gaps_opened"][0]
                self.assertEqual(main(["gaps", pid, "--id", gap_id, "--disposition", "accepted"]), 0)
            base = tmp / "workspaces" / pid
            self.assertEqual(len(first["gaps_opened"]), 1)
            self.assertTrue(first["gaps_opened"][0].startswith("GAP-SUF-"))
            self.assertEqual([r["reason"] for r in first["rejected"]], ["the text that would resolve it is already in the brief"])
            self.assertFalse(first["sufficient"])
            self.assertTrue(second["sufficient"])
            rows = {g["id"]: g for g in parse_gap_table((base / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
            self.assertEqual(rows[gap_id]["origin"], "sufficiency")
            self.assertEqual(rows[gap_id]["kind"], "synthesis")
            log = (base / "01_discovery" / "sufficiency_log.md").read_text(encoding="utf-8")
            self.assertIn("## Round 1", log)
            self.assertIn("verdict: SUFFICIENT", log)
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
