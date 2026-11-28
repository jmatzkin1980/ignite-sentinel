"""IMP-416 (H27 inc 5b): the walk of a change from the consolidated request to its stories, through the CLI.

`/specs --change` writes the document by functionality (eight blocks, the traceability row of the replaced rule with its
line), `/backlog --change` cuts the stories by functionality and delta and writes the change's own slice plan, and
`/next --change` leaves the backlog step. Synthetic Compras / alta de proveedores domain.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import class_deferred, complete_extraction, run_ok, waive_coherence, waive_crosses  # noqa: E402
from test_h27_consolidated_export import FinalCase  # noqa: E402
from test_h27_consolidation import CID, PID  # noqa: E402

from sentinel.compilers.change_backlog import read_change_units  # noqa: E402
from sentinel.compilers.change_spec_doc import BLOCKS  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402


class FunctionalSpecsWalk(FinalCase):
    def setUp(self):
        super().setUp()
        self.submit_text(self.rep())
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
        run_ok(["sources", PID, "--change", CID, "--no-baseline", "--reason", "el sistema actual no tiene documentación (prueba)"])
        waive_crosses(PID, CID)
        waive_coherence(PID, CID)
        complete_extraction(PID, CID, skip=("RN-02", "RN-06"))
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-item", "HU-03"])  # the one the extraction flagged
        # IMP-435 (B-22): PD-01 still holds the losing figure of the same decision; it is consolidated too
        result = self.submit_text("\n".join(["### PD-01", f"- Decisión: {self.dis}", f"- Líneas: {self.lines_of('PD-01')}",
                                    "- Texto: El umbral de aprobación se configura por parámetro y arranca en 1.000.000.", ""]), "pd.md")
        self.assertEqual(result["recorded"], ["PD-01"], result)
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "PD-01"])
        run_ok(["brief", PID, "--change", CID])
        forget_read_snapshots()
        class_deferred(PID, CID)
        # the request has nothing for the section of the process: that mark is the only thing the final waits for
        with patch("sentinel.deliverables.gate", return_value={"deliverable": "final", "pending_marks": 0}):
            run_ok(["export", PID, "--artifact", "brief", "--change", CID, "--final"])
        forget_read_snapshots()
        run_ok(["specs", PID, "--change", CID])
        self.base = workspace_path(PID)

    def test_specs_by_functionality(self):
        text = (self.base / "03_specs" / CID / "specs.md").read_text(encoding="utf-8")
        found = re.search(r"^## FUN-\d+ — Aprobación por monto \(", text, re.M)
        self.assertIsNotNone(found, text)
        start = text.index(found.group(0))
        end = text.find("\n## ", start + 1)
        section = text[start:end if end >= 0 else len(text)]
        self.assertEqual(re.findall(r"^### (.+)$", section, re.M), BLOCKS["es"])
        row = next(line for line in text.split("## Trazabilidad", 1)[1].splitlines() if "| RN-02 |" in line)
        self.assertIn(":L31", row)

    def test_backlog_by_slices_and_own_plan(self):
        units = read_change_units(PID, CID)
        forget_read_snapshots()
        res = json.loads(run_ok(["backlog", PID, "--change", CID]))
        self.assertTrue(res["stories"])
        self.assertLessEqual(len(res["stories"]), len(units))
        self.assertEqual(len(res["stories"]), len(res["slices"]))  # one story per cut of plan_change_slices
        covered = [unit for story in res["slices"].values() for unit in story["units"]]
        self.assertEqual(sorted(covered), sorted(u["id"] for u in units))
        self.assertTrue((self.base / "04_backlog" / CID / "SLICE-PLAN.md").exists())
        self.assertFalse((self.base / "04_backlog" / "SLICE-PLAN.md").exists())

    def test_next_leaves_the_backlog(self):
        forget_read_snapshots()
        run_ok(["backlog", PID, "--change", CID])
        forget_read_snapshots()
        step = json.loads(run_ok(["next", PID, "--change", CID]))
        self.assertEqual(step["key"], "quality", step)  # IMP-431: the audit comes between the backlog and the validation


if __name__ == "__main__":
    unittest.main()
