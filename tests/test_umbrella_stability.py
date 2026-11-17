"""IMP-344: a brief v2 umbrella gap does not move under the BA.

Before, a pending place with no routed gap pointed at its lens's default gap (for example
§3.1 at `GAP-PRODUCT-ASIS-TOBE`, which is routed to §3.2). Answering that gap filled §3.2 only,
so §3.1 lost its open gap and fell to a section umbrella `GAP-BRIEF-S3` that did not exist a
moment before: a closed round reopened or grew. Now a place points at a gap whose answer fills
it, else at its section umbrella from the first compile, so answering any other gap leaves the
umbrellas as they were.
"""

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

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / "fixtures" / "evals" / "support-dashboard" / "requirement.md"

ANSWERS = """# SYNTHETIC answers (not client data)

### GAP-PRODUCT-ASIS-TOBE
- Answer: Today team leads copy three ticket exports into a spreadsheet; tomorrow they open one dashboard view.
- Owner / source: Synthetic client round
- Evidence or reference: Synthetic umbrella-stability fixture
- Decision status: confirmed

### GAP-DESIGN-FLOW
- Answer: The team lead opens the overview, picks a queue and reads its ageing chart.
- Owner / source: Synthetic client round
- Evidence or reference: Synthetic umbrella-stability fixture
- Decision status: confirmed
"""


class UmbrellaStabilityTest(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.tmp = Path(tempfile.mkdtemp())
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, argv):
        from sentinel.cli import main

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(argv), 0, argv)
        text = out.getvalue()
        return json.loads(text[text.index("{"):])

    def test_answering_a_routed_gap_does_not_open_or_grow_an_umbrella(self):
        from sentinel.brief_model import V2_GAP_ROUTES
        from sentinel.compilers.brief_v2 import UMBRELLA_PREFIX
        from sentinel.gaps import parse_gap_table
        from sentinel.memory import ContextBroker

        pid = "UMB"
        base = self.tmp / "workspaces" / pid
        report_path = base / "02_requirements" / "brief_compile_report.json"
        answers = self.tmp / "answers.md"
        answers.write_text(ANSWERS, encoding="utf-8")
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            self.run_cli(["init", pid])
            self.run_cli(["ingest", pid, "--source", str(FIXTURE)])
            self.run_cli(["brief", pid, "--profile", "UI", "--genesis", "greenfield"])
            before = json.loads(report_path.read_text(encoding="utf-8"))
            # every pending mark points at a gap its answer fills, or at its section umbrella
            for site in before["fill_sites"]:
                place = str(site["id"]).split("/")[0]
                gap = site["gap"]
                if gap.startswith(UMBRELLA_PREFIX) or gap not in V2_GAP_ROUTES:
                    continue
                self.assertEqual(V2_GAP_ROUTES[gap], place, f"{site['id']} points at {gap}")
            resolved = self.run_cli(["resolve-gaps", pid, "--source", str(answers)])
        after = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(sorted(resolved["closed"]), ["GAP-DESIGN-FLOW", "GAP-PRODUCT-ASIS-TOBE"])
        umbrellas_before = before["umbrella_gaps"]
        for gap, places in after["umbrella_gaps"].items():
            self.assertIn(gap, umbrellas_before, f"{gap} appeared after answering other gaps")
            self.assertLessEqual(set(places), set(umbrellas_before[gap]), f"{gap} grew")
        rows = {g["id"]: g for g in parse_gap_table((base / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
        for gap in umbrellas_before:
            self.assertNotEqual(rows[gap]["status"], "CLOSED", gap)  # nothing answered them

    def test_umbrella_question_names_each_place(self):
        from sentinel.brief_schema import load_brief_schema
        from sentinel.compilers.brief_v2 import _place_title
        from sentinel.gaps import parse_gap_table
        from sentinel.memory import ContextBroker

        pid = "UMBQ"
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            self.run_cli(["init", pid])
            self.run_cli(["ingest", pid, "--source", str(FIXTURE)])
            self.run_cli(["brief", pid, "--profile", "UI", "--genesis", "greenfield"])
        base = self.tmp / "workspaces" / pid
        report = json.loads((base / "02_requirements" / "brief_compile_report.json").read_text(encoding="utf-8"))
        rows = {g["id"]: g for g in parse_gap_table((base / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
        schema = load_brief_schema()
        self.assertTrue(report["umbrella_gaps"])
        for gap, places in report["umbrella_gaps"].items():
            question = rows[gap]["question"]
            self.assertNotIn("brief v2", question)
            for place in places:
                title = _place_title(schema, place, "en")
                self.assertTrue(title, place)
                self.assertIn(f"{place} {title}", question)


if __name__ == "__main__":
    unittest.main()
