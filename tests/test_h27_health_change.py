"""IMP-406 (H27 inc 1) task 2: a workspace of changes keeps health honest and /status --change explains a dirty one."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_ok  # noqa: E402
from test_backlog_hooks import EARS, RAW  # noqa: E402

from sentinel.health import collect_health, health_explanation, reconcile_change_only_health  # noqa: E402
from sentinel.workspace import read_state, update_state  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PID = "HLTC"
CID = "CHG-001"


def status_change() -> dict:
    return json.loads(run_ok(["status", PID, "--change", CID]))


class ChangeHealth(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_extraction" / "pedido_ids.md", root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])

    def test_ingest_change_leaves_health_clean(self):
        self.assertEqual(read_state(PID)["health"], "CLEAN")
        self.assertEqual(collect_health(PID)["findings"], [])

    def test_change_commands_keep_it_clean(self):
        root = Path.cwd()
        run_ok(["resolve-gaps", PID, "--source", str(root / "scope.md"), "--change", CID])
        run_ok(["sources", PID, "--load", str(FIXTURES / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base", "--change", CID])
        status = status_change()
        self.assertEqual(status["health"], "CLEAN")
        self.assertNotIn("health_detail", status)

    def test_status_explains_a_finding(self):
        update_state(PID, health="DIRTY")
        real = collect_health(PID)
        fake = {**real, "findings": ["CHG-001 is not indexed in memory."]}
        with patch("sentinel.health.collect_health", return_value=fake):
            detail = health_explanation(PID)
        self.assertEqual(detail["command"], f"/reindex {PID}")
        self.assertIn("Run /reindex", detail["text"])
        self.assertEqual(detail["title"], "Index what the last commands recorded")

    def test_status_explains_the_initial_state(self):
        update_state(PID, health="DIRTY")
        status = status_change()
        self.assertEqual(status["health"], "DIRTY")
        detail = status["health_detail"]
        self.assertEqual(detail["command"], f"/health {PID}")
        self.assertIn("/init", detail["text"])

    def test_recompute_turns_dirty_into_a_verdict(self):
        update_state(PID, health="DIRTY")
        self.assertEqual(reconcile_change_only_health(PID), "CLEAN")
        self.assertEqual(read_state(PID)["health"], "CLEAN")
        self.assertIsNone(reconcile_change_only_health(PID))


class ProjectWorkspace(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_matured_workspace("HLTP", RAW, gap_acceptance_answer(EARS), backlog=False)

    def test_project_workspace_is_untouched(self):
        with patch("sentinel.health.run_health") as health:
            run_ok(["resolve-gaps", "HLTP", "--source", str(Path.cwd() / "answers.md")])
            health.assert_not_called()
        status = json.loads(run_ok(["status", "HLTP"]))
        self.assertNotIn("health_detail", status)


if __name__ == "__main__":
    unittest.main()
