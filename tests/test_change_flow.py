"""IMP-382: the change path end to end, and the workspace it leaves passes /doctor and /status."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from test_change_border import GOOD_BORDER, scope_answer  # noqa: E402

from sentinel.changes import get_change  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class ChangeFlow(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(scope_answer(GOOD_BORDER), encoding="utf-8")
        run_ok(["init", "BORR"])

    def test_borrador_end_to_end(self):
        out = json.loads(run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"]))
        cid = out["change_id"]
        self.assertLessEqual(out["gap_counts"]["total"], 4)  # scope round
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", cid])
        counts = get_change("BORR", cid)["gap_counts"]
        self.assertLessEqual(counts["total"], 20)  # 27 on the project path
        self.assertIn(json.loads(run_ok(["doctor"]))["verdict"], {"PASS", "WARN"})
        status = json.loads(run_ok(["status", "BORR"]))
        self.assertEqual(status["project_id"], "BORR")


if __name__ == "__main__":
    unittest.main()
