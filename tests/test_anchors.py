"""IMP-258: anchors that hold. The seeded-defect evals run here too, and a compiled
brief v2 holds every anchor."""

import sys
import unittest
from pathlib import Path

from sentinel.anchors import anchor_report, exempt_data
from sentinel.compilers.brief_v2 import render_brief_v2

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))
from test_brief_v2_compiler import inputs  # noqa: E402


class AnchorEvalTests(unittest.TestCase):
    def test_every_seeded_case_matches_exactly(self):
        import run_anchor_evals

        result = run_anchor_evals.run()
        self.assertGreaterEqual(len(result["cases"]), 8)
        self.assertEqual({case["split"] for case in result["cases"]}, {"tuning", "held_out"})
        for case in result["cases"]:
            with self.subTest(case=case["case"]):
                self.assertTrue(case["ok"], case)


class CompiledBriefTests(unittest.TestCase):
    def test_a_compiled_brief_holds_every_anchor(self):
        for language in ("en", "es"):
            data = inputs(language=language)
            report = anchor_report(render_brief_v2(data)[0], data.registry)
            with self.subTest(language=language):
                self.assertEqual(report["findings"], [])
                self.assertGreater(report["sites"], 0)
                self.assertEqual(report["sites"], report["holding"])

    def test_a_retired_source_breaks_the_count(self):
        data = inputs()
        registry = [dict(row, validity="retired") if row["id"] == "F-01" else row for row in data.registry]
        report = anchor_report(render_brief_v2(data)[0], registry)
        self.assertLess(report["holding"], report["sites"])
        self.assertTrue(all(f["code"] == "stale_source" for f in report["findings"]))

    def test_v1_is_never_checked(self):
        self.assertEqual(anchor_report("# Brief\n\n## 1. Identity\n\n- A claim.\n", []),
                         {"findings": [], "sites": 0, "holding": 0})

    def test_the_exempt_list_is_closed_data(self):
        data = exempt_data()
        self.assertEqual(set(data["places"]), {"0.1", "0.2", "6.3", "7.1", "7.2", "8.1", "A.provenance"})
        self.assertEqual(set(data["line_kinds"]),
                         {"heading", "table", "pending", "na", "inferred", "reference", "out_of_scope", "verdict"})


if __name__ == "__main__":
    unittest.main()
