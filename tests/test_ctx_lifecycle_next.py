"""IMP-294: the CTX-NNN lifecycle and `/next`."""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sentinel.cli import main
from sentinel.context_requests import (
    CTX_TRANSITIONS,
    context_request_summary,
    load_ctx_lifecycle,
    transition_context_request,
)
from sentinel.core.graph import nodes_by_type
from sentinel.mcp import describe_tools, run_cli
from sentinel.status import project_next, project_status
from sentinel.sync import sync_change

ROOT = Path(__file__).resolve().parents[1]
RAW = "# Billing Portal\n\nFinance users review monthly invoices before approval. Approval must be logged.\n"


def _run(argv: list[str]) -> tuple[int, dict]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(argv)
    text = out.getvalue()
    return code, (json.loads(text[text.index("{"):]) if "{" in text else {})


class LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "billing.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(_run(["init", "CTXL"])[0], 0)
        self.assertEqual(_run(["ingest", "CTXL", "--source", str(raw)])[0], 0)
        code, result = _run(["context-request", "CTXL", "--domain", "technology"])
        self.assertEqual(code, 0)
        self.ctx = result["context_request_id"]

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _status(self) -> str:
        return next(node for node in nodes_by_type("CTXL", "context_request") if node["id"] == self.ctx)["status"]

    def test_a_request_is_born_active(self) -> None:
        self.assertEqual(self._status(), "active")
        self.assertEqual(context_request_summary("CTXL")["active"], 1)

    def test_sync_citing_the_ctx_marks_it_answered(self) -> None:
        reply = self.temp / "01_meetings" / "tech-reply.md"
        reply.parent.mkdir()
        reply.write_text(f"# Reply to {self.ctx}\n\nThe stack is Postgres and Python.\n", encoding="utf-8")
        result = sync_change("CTXL", reply, "tech reply")
        self.assertEqual(result["answered_context_requests"], [self.ctx])
        self.assertEqual(self._status(), "answered")
        history = load_ctx_lifecycle("CTXL")[self.ctx]["history"]
        self.assertEqual((history[0]["from"], history[0]["to"]), ("active", "answered"))
        self.assertTrue(history[0]["via"].startswith("sync CHG-"))

        again = self.temp / "01_meetings" / "tech-reply-2.md"
        again.write_text(f"# More on {self.ctx}\n", encoding="utf-8")
        self.assertEqual(sync_change("CTXL", again, "more")["answered_context_requests"], [])  # only active moves

    def test_a_change_that_does_not_cite_it_leaves_it_alone(self) -> None:
        other = self.temp / "01_meetings" / "other.md"
        other.parent.mkdir()
        other.write_text("# Notes\n\nCTX-0999 and XCTX-001 are not this request.\n", encoding="utf-8")
        self.assertEqual(sync_change("CTXL", other, "x")["answered_context_requests"], [])
        self.assertEqual(self._status(), "active")

    def test_transitions(self) -> None:
        with self.assertRaisesRegex(ValueError, "can move to: answered, obsolete"):
            transition_context_request("CTXL", self.ctx, "closed", "too early")
        transition_context_request("CTXL", self.ctx, "answered")
        transition_context_request("CTXL", self.ctx, "active")  # the answer fell short
        transition_context_request("CTXL", self.ctx, "answered")
        with self.assertRaisesRegex(ValueError, "needs --reason"):
            transition_context_request("CTXL", self.ctx, "closed")
        transition_context_request("CTXL", self.ctx, "closed", "domain owner confirmed")
        with self.assertRaisesRegex(ValueError, "none, it is final"):
            transition_context_request("CTXL", self.ctx, "active")
        steps = [(h["from"], h["to"]) for h in load_ctx_lifecycle("CTXL")[self.ctx]["history"]]
        self.assertEqual(steps, [("active", "answered"), ("answered", "active"), ("active", "answered"), ("answered", "closed")])
        self.assertEqual(CTX_TRANSITIONS["obsolete"], ())

    def test_cli_obsolete_and_regenerate_reopens(self) -> None:
        self.assertEqual(_run(["context-request", "CTXL", "--id", self.ctx, "--status", "obsolete"])[0], 1)  # no reason
        code, result = _run(["context-request", "CTXL", "--id", self.ctx, "--status", "obsolete", "--reason", "scope dropped"])
        self.assertEqual((code, result["to"]), (0, "obsolete"))
        self.assertEqual(_run(["context-request", "CTXL", "--id", self.ctx])[0], 1)  # --id needs --status
        self.assertEqual(_run(["context-request", "CTXL"])[0], 1)  # needs --domain or --id
        self.assertEqual(_run(["context-request", "CTXL", "--id", "CTX-999", "--status", "answered"])[0], 1)
        code, result = _run(["context-request", "CTXL", "--domain", "technology"])
        self.assertEqual(result["context_request_id"], self.ctx)
        self.assertEqual(self._status(), "active")
        self.assertEqual(load_ctx_lifecycle("CTXL")[self.ctx]["history"][-1]["via"], "context-request (regenerated)")

    def test_mcp_moves_a_ctx(self) -> None:
        result = run_cli(["context-request", "CTXL", "--id", self.ctx, "--status", "answered"])
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["output"]["to"], "answered")


class NextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(_run(["init", "NXT"])[0], 0)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _assert_same_everywhere(self) -> str:
        expected = project_status("NXT", full=False)["next_action"]
        self.assertEqual({k: v for k, v in project_next("NXT").items() if k != "project_id"}, expected)
        code, cli = _run(["next", "NXT"])
        self.assertEqual(code, 0)
        self.assertEqual({k: v for k, v in cli.items() if k != "project_id"}, expected)
        mcp = run_cli(["next", "NXT"])
        self.assertEqual({k: v for k, v in mcp["output"].items() if k != "project_id"}, expected)
        return expected["key"]

    def test_next_equals_status_at_each_stage(self) -> None:
        self.assertEqual(self._assert_same_everywhere(), "ingest")
        raw = self.temp / "billing.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(_run(["ingest", "NXT", "--source", str(raw)])[0], 0)
        self.assertNotEqual(self._assert_same_everywhere(), "ingest")

    def test_next_is_read_only(self) -> None:
        # Like /status, the command protocol logs the call (last_command*, command_log); nothing else moves.
        state = self.temp / "workspaces" / "NXT" / "state.json"
        strip = lambda data: {k: v for k, v in data.items() if not k.startswith(("last_command", "command_log"))}
        before = strip(json.loads(state.read_text(encoding="utf-8")))
        _run(["next", "NXT"])
        self.assertEqual(strip(json.loads(state.read_text(encoding="utf-8"))), before)

    def test_next_on_all_four_surfaces(self) -> None:
        self.assertIn("sentinel_next", {tool["name"] for tool in describe_tools()})
        for path in (".claude/commands/next.md", ".kilo/commands/next.md"):
            text = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("python -m sentinel /next PROJECT_ID", text, path)


if __name__ == "__main__":
    unittest.main()
