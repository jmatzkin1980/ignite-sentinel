"""IMP-26u (H16c close): the round → answer → fewer `⏳` circuit, on a SYNTHETIC answered round.

The answers in `fixtures/synthetic_answered_round/answers.md` are invented. They answer the first
`/gaps --top 5` round of the support-dashboard eval fixture so the test proves the mechanism: every
answered gap lands in its brief v2 place (routed, umbrella place by place, counterpart as a
complement, delivery under §9.1) and the marks it held go away. The real drop is measured on the
first real project.
"""

import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / "fixtures" / "evals" / "support-dashboard" / "requirement.md"
ANSWERS = ROOT / "fixtures" / "synthetic_answered_round" / "answers.md"


class AnsweredRoundTest(unittest.TestCase):
    def test_umbrella_answer_splits_by_place_within_its_section(self):
        from sentinel.compilers.brief_v2 import umbrella_places

        self.assertEqual(umbrella_places("GAP-BRIEF-S1", "1.2: The pain. 1.4: Start; end. 2.3: Not mine."),
                         {"1.2": "The pain.", "1.4": "Start; end."})
        self.assertEqual(umbrella_places("GAP-BRIEF-S1", "No place prefix at all."), {})
        self.assertEqual(umbrella_places("GAP-USERS", "1.2: routed gaps are not umbrellas"), {})

    def test_answered_round_lowers_pending_marks(self):
        from sentinel.brief_integrity import brief_v2_integrity_findings
        from sentinel.cli import main
        from sentinel.gaps import parse_gap_table
        from sentinel.memory import ContextBroker

        pid = "ROUND"
        old_cwd = Path.cwd()
        tmp = Path(tempfile.mkdtemp())
        os.chdir(tmp)
        out = io.StringIO()

        def run(argv):
            out.truncate(0)
            out.seek(0)
            self.assertEqual(main(argv), 0, argv)
            text = out.getvalue()
            return json.loads(text[text.index("{"):])

        try:
            with patch.object(ContextBroker, "_connect_lancedb", lambda self: None), contextlib.redirect_stdout(out):
                run(["init", pid])
                run(["ingest", pid, "--source", str(FIXTURE)])
                run(["brief", pid, "--profile", "UI", "--genesis", "greenfield"])
                base = tmp / "workspaces" / pid
                report = base / "02_requirements" / "brief_compile_report.json"
                before = json.loads(report.read_text(encoding="utf-8"))
                round_ = run(["gaps", pid, "--top", "5"])
                resolved = run(["resolve-gaps", pid, "--source", str(ANSWERS)])
            after = json.loads(report.read_text(encoding="utf-8"))
            answered = re.findall(r"^### (GAP-[A-Z0-9-]+)", ANSWERS.read_text(encoding="utf-8"), re.M)
            # the fixture answers exactly the round the runtime asks
            self.assertEqual(sorted(item["id"] for item in round_["round"]), sorted(answered))
            self.assertEqual(sorted(resolved["closed"]), sorted(answered))
            self.assertEqual(resolved["closure_findings"], [])

            b, a = before["summary"], after["summary"]
            self.assertLess(a["pending_client"], b["pending_client"])
            self.assertLess(a["pending_domain"], b["pending_domain"])
            self.assertGreater(a["covered"], b["covered"])
            # every answered place is settled: no mark points to an answered gap any more
            still = {site["gap"] for site in after["fill_sites"]}
            self.assertFalse(still & set(answered), still & set(answered))
            brief = (base / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
            for text in ("Team leads assemble the weekly review by hand", "Weeks run Monday to Sunday",
                         "more than 10 percent of its open tickets", "the ticketing tool remains the system of record",
                         "The first slice is the read-only queue overview"):
                self.assertIn(text, brief)
            self.assertIn("Out of scope: editing tickets", brief)  # the counterpart completes, it does not replace
            rows = {g["id"]: g for g in parse_gap_table((base / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
            self.assertEqual(rows["GAP-BRIEF-S1"]["status"], "CLOSED")
            self.assertEqual(rows["GAP-BRIEF-S2"]["status"], "CLOSED")
            # the recompiled brief has a §6.3 cascade table and stays clean (no em dash cells)
            self.assertIn("| Place | Change | Propagate to |", brief)
            self.assertEqual(brief_v2_integrity_findings(base), [])
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
