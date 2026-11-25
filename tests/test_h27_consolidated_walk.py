"""IMP-414 (H27 inc 5a) task 7: the walk of the consolidated final brief and the change PRD, by CLI."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
import test_change_next  # noqa: E402
import test_h27_consolidated_export  # noqa: E402
import test_h27_consolidation_control  # noqa: E402
from test_h26_cross_record import CID, PID  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

CONSOLIDATED = "mayor a 1.000.000 requiere aprobación de la jefa de Compras"
ORIGINAL = "mayor a 5.000.000 requiere aprobación de la jefa de Compras"


class ConsolidatedWalk(test_h27_consolidated_export.FinalCase):
    step_key = test_h27_consolidation_control.Control.step_key
    earlier_gates_done = test_h27_consolidation_control.Control.earlier_gates_done

    def test_walk(self):
        # the closed design decision touches RN-02 and chose no option that keeps the request text
        with self.earlier_gates_done():
            self.assertEqual(self.step_key(), "consolidate")
            result = self.submit_text(self.rep())  # `extract --consolidate` with the block of RN-02
            self.assertEqual(result["recorded"], ["RN-02"], result)
            self.assertEqual(self.step_key(), "consolidate_confirm")
            forget_read_snapshots()
            step = json.loads(run_ok(["next", PID, "--change", CID]))
            self.assertEqual(step["key"], "consolidate_confirm")
            self.assertIn("RN-02", step["command"])
            forget_read_snapshots()
            done = json.loads(run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"]))
            self.assertEqual(done["action"], "confirm_replacement")
        forget_read_snapshots()
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertGreaterEqual(status["consolidation"]["modificado"], 1)
        self.assertEqual(status["consolidation"]["unconfirmed"], [])

        # the working export is the draft with the EARS rows; the final one is the consolidated text
        forget_read_snapshots()
        run_ok(["brief", PID, "--change", CID])
        forget_read_snapshots()
        exported = json.loads(run_ok(["export", PID, "--artifact", "brief", "--change", CID]))
        work = (workspace_path(PID) / exported["path"]).read_text(encoding="utf-8") if not Path(exported["path"]).is_absolute() \
            else Path(exported["path"]).read_text(encoding="utf-8")
        self.assertIn("REQ-EARS-", work)
        final = self.final()
        self.assertIn(CONSOLIDATED, final)
        self.assertNotIn(ORIGINAL, final)
        self.assertIn("No entra: RN-06", final)
        self.assertIn("## A.decisions", final)
        self.assertNotIn("REQ-EARS-", final)


class WalkReachesDoneWithThePrd(test_change_next.ChangeNextSequence):
    def test_each_row_of_the_table_in_order(self):
        super().test_each_row_of_the_table_in_order()
        status = json.loads(run_ok(["status", "BORR", "--change", CID]))
        self.assertEqual(status["next_action"]["key"], "done")
        self.assertTrue((workspace_path("BORR") / "03_specs" / CID / "prd.md").is_file())


def load_tests(loader, tests, pattern):
    """Only the walks of this file: the classes they extend carry tests that have their own modules."""
    suite = unittest.TestSuite()
    suite.addTest(ConsolidatedWalk("test_walk"))
    suite.addTest(WalkReachesDoneWithThePrd("test_each_row_of_the_table_in_order"))
    return suite


if __name__ == "__main__":
    unittest.main()
