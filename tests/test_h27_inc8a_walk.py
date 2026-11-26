"""H27 inc 8a walk: a change-only workspace, from its backlog to its quality verdict, and what the project forms refuse."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (  # noqa: E402
    SnapshotWorkspaceCase, class_deferred, complete_extraction, export_final_brief, run_ok, waive_coherence, waive_crosses,
)
from sentinel.commands import skill_for_command  # noqa: E402
from sentinel.workspace import read_json, workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402
from test_change_next import FIXTURES, cli_json, load_baseline  # noqa: E402
from test_change_specs import ALL_ANSWERS, answer  # noqa: E402
from test_h27_change_release import cli  # noqa: E402

PID = "BORR"
CID = "CHG-001"
ROOT = Path(__file__).resolve().parents[1]


def next_step() -> dict:
    return cli_json(["next", PID, "--change", CID])


class Inc8aWalk(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        waive_crosses(PID, CID)
        load_baseline(PID)
        answer(PID, CID, "a.md", ALL_ANSWERS)
        waive_coherence(PID, CID)
        complete_extraction(PID, CID)
        run_ok(["brief", PID, "--change", CID])
        class_deferred(PID, CID)
        export_final_brief(PID, CID)
        run_ok(["specs", PID, "--change", CID])

    def test_walk(self) -> None:
        run_ok(["backlog", PID, "--change", CID])
        self.assertEqual(next_step()["key"], "quality")
        audited = json.loads(run_ok(["quality", PID, "--change", CID]))
        self.assertEqual(audited["change_id"], CID)
        self.assertEqual(next_step()["key"], "done")
        status = cli_json(["status", PID, "--change", CID])
        self.assertIn(status["quality"]["verdict"], ("PASS", "PARTIAL", "ATTENTION"))
        self.assertTrue(status["quality"]["current"])
        before = read_json(workspace_path(PID) / "state.json", {})
        report = workspace_path(PID) / "01_discovery" / "requirement_maturity_report.md"
        code, out = cli(["maturity", PID])
        self.assertNotEqual(code, 0, out)
        self.assertIn(f"/status {PID} --change {CID}", out)
        self.assertFalse(report.exists())
        after = read_json(workspace_path(PID) / "state.json", {})
        for key in ("phase", "health", "maturity_metrics"):
            self.assertEqual(after.get(key), before.get(key), key)
        code, out = cli(["quality", PID])
        self.assertNotEqual(code, 0, out)
        self.assertIn(f"/quality {PID} --change {CID}", out)

    def test_quality_is_routed_to_its_change_section(self) -> None:
        self.assertEqual(skill_for_command(f"/quality {PID} --change {CID}"), "sentinel-quality §Change")
        skill = (ROOT / ".codex" / "skills" / "sentinel-quality" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## Change (`--change CHG-NNN`)", skill)
        manifest = json.loads((ROOT / "sentinel" / "templates" / "commands_manifest.json").read_text(encoding="utf-8"))
        entries = manifest["commands"] if isinstance(manifest, dict) and "commands" in manifest else manifest
        quality = next(entry for entry in entries if entry["name"] == "quality")
        self.assertIn("--change CHG-NNN", quality["argument_hint"])
        self.assertIn("/quality PROJECT_ID --change CHG-NNN", quality["body"])


if __name__ == "__main__":
    unittest.main()
