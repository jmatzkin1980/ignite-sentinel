"""IMP-396: `/next` and `/status` know the change: one step per row of its sequence, never the PRD."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_cli, run_ok  # noqa: E402
from sentinel import mcp as sentinel_mcp  # noqa: E402
from sentinel.readiness_verdict import changes_overview, change_next_step  # noqa: E402
from sentinel.workspace import read_json, update_state, workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402
from test_change_affected_stories import ANSWERS as REMOVED_ANSWERS  # noqa: E402
from test_change_specs import ACCEPTANCE, ALL_ANSWERS, EXTRA, PROJECT_EARS, PROJECT_RAW, answer, open_change  # noqa: E402
from test_mcp_parity import _tools  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CID = "CHG-001"
SAD = FIXTURES / "change_baseline" / "sad-compras.md"


def load_baseline(project: str, cid: str = CID) -> None:
    """IMP-400: the `baseline` step comes after scope; these tests load it through the CLI to reach the later steps."""
    run_ok(["sources", project, "--load", str(SAD), "--role", "linea_de_base", "--change", cid])


def step(project: str = "BORR", cid: str = CID) -> dict:
    return change_next_step(project, cid)


def cli_json(argv: list[str]) -> dict:
    code, out = run_cli(argv)
    assert code == 0, (argv, code, out)
    return json.loads(out)


def set_change(project: str, cid: str = CID, **fields) -> None:
    changes = read_json(workspace_path(project) / "state.json", {})["changes"]
    changes[cid].update(fields)
    update_state(project, changes=changes)


def requirements_path(project: str = "BORR") -> Path:
    return workspace_path(project) / "02_requirements" / CID / "requirements.md"


class ChangeNextSequence(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])

    def test_each_row_of_the_table_in_order(self):
        s = step()
        self.assertEqual((s["key"], s["change_id"]), ("scope", CID))
        self.assertEqual(s["command"], f"/resolve-gaps BORR --source PATH --change {CID}")
        self.assertIn("GAP-SCOPE", s["text"])

        (Path.cwd() / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", CID])
        s = step()
        self.assertEqual((s["key"], s["command"]), (
            "baseline", f"/sources BORR --load PATH --role linea_de_base --change {CID}"))
        load_baseline("BORR")
        s = step()
        self.assertEqual(s["key"], "lenses")
        self.assertEqual(s["command"], f"/resolve-gaps BORR --source PATH --change {CID}")

        answer("BORR", CID, "a.md", ALL_ANSWERS)
        s = step()
        self.assertEqual((s["key"], s["command"]), ("brief", f"/brief BORR --change {CID}"))

        run_ok(["brief", "BORR", "--change", CID])
        rows = requirements_path().read_text(encoding="utf-8")
        kept = [ln for ln in rows.splitlines() if "| ADDED |" not in ln and "| MODIFIED |" not in ln]
        requirements_path().write_text("\n".join(kept) + "\n", encoding="utf-8")
        s = step()
        self.assertEqual(s["key"], "requirements")
        self.assertIn("Delta", s["text"])
        self.assertIn("Superficie", s["text"])
        requirements_path().write_text(rows, encoding="utf-8")

        s = step()
        self.assertEqual((s["key"], s["command"]), ("specs", f"/specs BORR --change {CID}"))

        run_ok(["specs", "BORR", "--change", CID])
        s = step()
        self.assertEqual((s["key"], s["command"]), ("backlog", f"/backlog BORR --change {CID}"))

        run_ok(["backlog", "BORR", "--change", CID])
        s = step()
        self.assertEqual(s["key"], "done")
        self.assertEqual(s["command"], "")
        self.assertNotIn("prd", " ".join(s.values()).lower())

    def test_stale_change_brief_sends_back_to_brief(self):
        # The brief was compiled with the 3 blocking gaps open; closing them leaves it stale.
        (Path.cwd() / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", CID])
        load_baseline("BORR")
        run_ok(["brief", "BORR", "--change", CID])
        report = workspace_path("BORR") / "02_requirements" / CID / "change_brief_report.json"
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["blocking_open"], 3)
        self.assertEqual(step()["key"], "lenses")
        answer("BORR", CID, "a.md", ALL_ANSWERS)
        s = step()
        self.assertEqual((s["key"], s["command"]), ("brief", f"/brief BORR --change {CID}"))
        self.assertIn("cambió el estado de los gaps", s["text"])
        self.assertEqual(cli_json(["next", "BORR", "--change", CID])["key"], "brief")
        run_ok(["brief", "BORR", "--change", CID])
        self.assertNotEqual(step()["key"], "brief")
        report.unlink()
        self.assertEqual(step()["key"], "brief")
        set_change("BORR", language="en")
        self.assertIn("state of the gaps changed", step()["text"])

    def test_specs_not_current_goes_back_to_specs(self):
        self.test_each_row_of_the_table_in_order()
        answer("BORR", CID, "b.md", EXTRA)
        self.assertEqual(step()["key"], "specs")

    def test_backlog_behind_the_specs(self):
        self.test_each_row_of_the_table_in_order()
        answer("BORR", CID, "b.md", EXTRA)
        run_ok(["specs", "BORR", "--change", CID])
        self.assertEqual(step()["key"], "backlog")
        run_ok(["backlog", "BORR", "--change", CID])
        self.assertEqual(step()["key"], "done")

    def test_validate_when_the_change_is_not_valid(self):
        self.test_each_row_of_the_table_in_order()
        story = workspace_path("BORR") / "04_backlog" / "US-002.md"
        lines = [ln.replace("pass-to-pass", "regression") if ln.startswith("| AC-002-06 |") else ln
                 for ln in story.read_text(encoding="utf-8").splitlines()]
        story.write_text("\n".join(lines) + "\n", encoding="utf-8")
        s = step()
        self.assertEqual((s["key"], s["command"]), ("validate", f"/validate BORR --change {CID}"))

    def test_change_only_workspace_never_says_ingest(self):
        out = cli_json(["next", "BORR"])
        self.assertEqual((out["key"], out["change_id"]), ("scope", CID))
        self.assertNotEqual(out["key"], "ingest")
        self.assertEqual(out["changes"][0]["next_step"]["key"], "scope")
        status = cli_json(["status", "BORR"])
        self.assertEqual(status["next_action"]["key"], "scope")
        self.assertEqual(status["next_action"]["change_id"], CID)
        self.assertNotIn("ingest", status["next_action"]["command"])
        self.assertEqual(status["changes"][0]["change_id"], CID)

    def test_change_only_picks_the_first_change_with_something_pending(self):
        self.test_each_row_of_the_table_in_order()
        out = cli_json(["next", "BORR"])
        self.assertEqual(out["key"], "done")  # every change is done: the first one is reported
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "otro.md")
        second = json.loads(run_ok(["ingest", "BORR", "--source", "otro.md", "--change"]))["change_id"]
        out = cli_json(["next", "BORR"])
        self.assertEqual((out["change_id"], out["key"]), (second, "scope"))

    def test_next_and_status_with_change(self):
        nxt = cli_json(["next", "BORR", "--change", CID])
        self.assertEqual((nxt["project_id"], nxt["change_id"], nxt["key"]), ("BORR", CID, "scope"))
        self.assertNotIn("changes", nxt)
        status = cli_json(["status", "BORR", "--change", CID])
        self.assertEqual((status["change_id"], status["round"]), (CID, "scope"))
        self.assertEqual(status["next_action"], {k: nxt[k] for k in ("change_id", "key", "title", "text", "command")})
        self.assertNotIn("verdict", status)

    def test_unknown_change_is_refused_like_elsewhere(self):
        for command in ("next", "status"):
            code, _ = run_cli([command, "BORR", "--change", "CHG-009"])
            self.assertEqual(code, run_cli(["specs", "BORR", "--change", "CHG-009"])[0], command)
            self.assertNotEqual(code, 0)

    def test_release_with_change_is_refused(self):
        for command in ("next", "status"):
            code, _ = run_cli([command, "BORR", "--change", CID, "--release", "r1"])
            self.assertEqual(code, 3, command)

    def test_english_follows_the_change_language(self):
        set_change("BORR", language="en")
        s = step()
        self.assertEqual(s["key"], "scope")
        self.assertIn("Close the change border", s["title"])
        self.assertIn("Answer GAP-SCOPE", s["text"])
        self.assertEqual(cli_json(["next", "BORR"])["title"], s["title"])

    def test_mcp_forwards_change(self):
        captured: list[list[str]] = []
        with patch.object(sentinel_mcp, "run_cli", lambda a: captured.append(a) or {"exit_code": 0}):
            _tools()["sentinel_next"](project_id="P", change=CID)
            _tools()["sentinel_status"](project_id="P", change=CID)
            _tools()["sentinel_next"](project_id="P")
        self.assertEqual(captured, [["next", "P", "--change", CID], ["status", "P", "--change", CID], ["next", "P"]])


class ChangeNextSeriesRelease(SnapshotWorkspaceCase):
    """A release verdict through the CLI (production fills `release` from the active scope) carries no `changes`."""

    @classmethod
    def build_workspace(cls):
        from test_release_split import VALID as SERIES  # noqa: PLC0415

        base = workspace_path("NOVA")
        run_ok(["init", "NOVA", "--brief-version", "1"])
        run_ok(["ingest", "NOVA", "--source", str(FIXTURES / "complete_requirement.md")])
        run_ok(["maturity", "NOVA"])
        (base / "02_requirements" / "project-brief.md").write_text(SERIES["brief"], encoding="utf-8")
        from sentinel.discovery import parse_gap_rows, render_gaps

        gaps = base / "01_discovery" / "gaps.md"
        rows = [r for r in parse_gap_rows(gaps.read_text(encoding="utf-8")) if r.get("id") != "NONE"]
        rows += [{"id": g, "lens": "business", "severity": "low", "status": "OPEN", "description": "synthetic gap",
                  "question": "Which?", "evidence_mention": "x", "origin": "agent", "resolution_note": ""}
                 for g in SERIES["open_gaps"]]
        gaps.write_text(render_gaps("NOVA", rows, "REQ-001", "en"), encoding="utf-8")
        Path("proposal.json").write_text(json.dumps(SERIES["payload"]), encoding="utf-8")
        run_ok(["split", "NOVA", "--propose", "--source", "proposal.json"])
        run_ok(["split", "NOVA", "--confirm", "--ba", "Ana", "--tech", "Core"])
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["ingest", "NOVA", "--source", "pedido.md", "--change"])

    def test_release_verdict_carries_no_changes(self):
        self.assertIn("changes", cli_json(["next", "NOVA"]))
        self.assertIn("changes", cli_json(["status", "NOVA"]))
        self.assertNotIn("changes", cli_json(["next", "NOVA", "--release", "r1"]))
        status = cli_json(["status", "NOVA", "--release", "r1"])
        self.assertNotIn("changes", status)
        self.assertNotIn("changes", status["verdict"])


class ChangeNextWarnings(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        run_ok(["init", "BORR"])
        open_change("BORR")

    def test_warnings_in_next_and_status(self):
        self.assertEqual(changes_overview("BORR")[0]["warnings"], [])
        load_baseline("BORR")  # no baseline would add its own warning: this test is about the escalation ones
        border = read_json(workspace_path("BORR") / "state.json", {})["changes"][CID]["border"]
        set_change("BORR", border=[*border, {"zone": "nuevo", "type": "rol", "name": "Auditor"}])
        (overview,) = changes_overview("BORR")
        self.assertEqual([w["trigger"] for w in overview["warnings"]], ["new_actors"])
        self.assertEqual(cli_json(["next", "BORR"])["changes"][0]["warnings"], overview["warnings"])
        self.assertEqual(cli_json(["next", "BORR", "--change", CID])["warnings"], overview["warnings"])
        self.assertEqual(cli_json(["status", "BORR"])["changes"][0]["warnings"], overview["warnings"])
        # IMP-402: /status --change also carries the extraction and preserved warnings; the escalation ones are the same
        own = [w for w in cli_json(["status", "BORR", "--change", CID])["warnings"]
               if not w["trigger"].startswith(("extraction_", "preserved_"))]
        self.assertEqual(own, overview["warnings"])


class ChangeNextMixed(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_matured_workspace("MIX", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS), backlog=False)

    def test_without_changes_no_key_and_same_step(self):
        nxt = cli_json(["next", "MIX"])
        self.assertNotIn("changes", nxt)
        self.assertEqual(nxt["key"], "backlog")
        status = cli_json(["status", "MIX"])
        self.assertNotIn("changes", status)
        self.assertNotIn("changes", status["verdict"])

    def test_with_a_change_the_project_step_stays_and_changes_is_added(self):
        before = cli_json(["next", "MIX"])
        cid = open_change("MIX")
        load_baseline("MIX", cid)
        nxt = cli_json(["next", "MIX"])
        self.assertEqual(nxt["key"], before["key"])
        self.assertEqual(nxt["command"], before["command"])
        self.assertNotIn("change_id", nxt)
        self.assertEqual([(c["change_id"], c["next_step"]["key"]) for c in nxt["changes"]], [(cid, "lenses")])
        status = cli_json(["status", "MIX"])
        self.assertEqual(status["next_action"]["key"], before["key"])
        self.assertEqual(status["changes"][0]["next_step"]["key"], "lenses")


class ChangeNextRemovedUnit(SnapshotWorkspaceCase):
    """A REMOVED row over only not-implemented stories produces no story: the backlog is not behind for it."""

    @classmethod
    def build_workspace(cls):
        build_matured_workspace("MIX", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS))
        cls.cid = open_change("MIX")
        load_baseline("MIX", cls.cid)
        answer("MIX", cls.cid, "a.md", REMOVED_ANSWERS)
        run_ok(["brief", "MIX", "--change", cls.cid])
        run_ok(["specs", "MIX", "--change", cls.cid])

    def test_dropped_unit_does_not_keep_next_on_backlog(self):
        self.assertEqual(change_next_step("MIX", self.cid)["key"], "backlog")
        run_ok(["backlog", "MIX", "--change", self.cid])
        backlog = read_json(workspace_path("MIX") / "state.json", {})["changes"][self.cid]["backlog"]
        self.assertEqual(len(backlog["dropped_units"]), 1)
        self.assertIn(change_next_step("MIX", self.cid)["key"], ("validate", "done"))
        self.assertIn(cli_json(["next", "MIX", "--change", self.cid])["key"], ("validate", "done"))
        self.assertIn(cli_json(["status", "MIX", "--change", self.cid])["next_action"]["key"], ("validate", "done"))

    def test_dropped_unit_gone_from_the_specs_is_ignored(self):
        run_ok(["backlog", "MIX", "--change", self.cid])
        set_change("MIX", self.cid, backlog={**read_json(workspace_path("MIX") / "state.json", {})["changes"][self.cid]["backlog"],
                                   "dropped_units": ["SPEC-U-099"]})
        self.assertEqual(change_next_step("MIX", self.cid)["key"], "backlog")

    def test_release_verdict_carries_no_changes(self):
        from sentinel.readiness_verdict import build_readiness_verdict

        self.assertIn("changes", build_readiness_verdict("MIX"))
        self.assertNotIn("changes", build_readiness_verdict("MIX", release="r1"))


if __name__ == "__main__":
    unittest.main()
