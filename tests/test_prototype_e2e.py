"""H17b closing check (IMP-27z): the prototype chain end to end.

A synthetic prototype, labelled as such, goes through the three modes of
`/prototype` in order: the inventory, the trace of one screen and the manual.
Each view matches its golden, and two runs in fresh workspaces are identical.

Regenerate the goldens on purpose with `SENTINEL_REGEN_GOLDEN=1`.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main

ROOT = Path(__file__).resolve().parent
PROTOTYPE = ROOT / "fixtures" / "synthetic_prototype" / "claims-portal.html"
TRACE = json.loads((ROOT / "fixtures" / "evals" / "prototype_trace" / "valid-trace.json").read_text(encoding="utf-8"))
GOLDEN = ROOT / "fixtures" / "golden" / "prototype"
VIEWS = ("inventory.md", "trace.md", "manual.md")
MANUAL = {
    "prototype": "F-01",
    "screens": [{
        "screen": "S2",
        "purpose": "Sign in to the portal before filing a claim, from {{S2-E01}}.",
        "steps": [{"text": "Type your email in {{S2-E03}}."},
                  {"text": "Type your password in {{S2-E05}} and press {{S2-E06}}."}],
        "notes": ["If you see {{S2-E07}}, check the email and the password and try again."],
    }],
}


def cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(list(argv))
    return code, out.getvalue()


def run_chain() -> dict[str, str]:
    """Run inventory -> trace of S2 -> manual in a fresh workspace and return the views."""
    from sentinel.discovery import render_gaps

    old = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            Path("claims-portal.html").write_text(PROTOTYPE.read_text(encoding="utf-8"), encoding="utf-8")
            steps = [("init", "P"), ("ingest", "P", "--source", "claims-portal.html"), ("prototype", "P", "--inventory")]
            for argv in steps:
                code, out = cli(*argv)
                if code != 0:
                    raise AssertionError(f"{argv}: {out}")
            base = Path("workspaces") / "P"
            (base / "02_requirements" / "project-brief.md").write_text(TRACE["brief"], encoding="utf-8")
            rows = [{"id": g, "lens": "design", "severity": "medium", "status": "OPEN", "description": "synthetic gap",
                     "question": "Which?", "evidence_mention": "§4.1", "origin": "agent", "resolution_note": ""}
                    for g in TRACE["open_gaps"]]
            (base / "01_discovery" / "gaps.md").write_text(render_gaps("P", rows, "REQ-001", "en"), encoding="utf-8")
            Path("trace.json").write_text(json.dumps(TRACE["payload"]), encoding="utf-8")
            Path("manual.json").write_text(json.dumps(MANUAL), encoding="utf-8")
            for argv in (("prototype", "P", "--trace", "--source", "trace.json"),
                         ("prototype", "P", "--manual", "--source", "manual.json")):
                code, out = cli(*argv)
                if code != 0:
                    raise AssertionError(f"{argv}: {out}")
            folder = base / "02_requirements" / "prototype"
            return {name: (folder / name).read_text(encoding="utf-8") for name in VIEWS}
        finally:
            os.chdir(old)


class PrototypeChainEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.first = run_chain()
        cls.second = run_chain()
        if os.environ.get("SENTINEL_REGEN_GOLDEN") == "1":
            GOLDEN.mkdir(parents=True, exist_ok=True)
            for name, text in cls.first.items():
                (GOLDEN / name).write_text(text, encoding="utf-8", newline="\n")

    def test_the_fixture_is_labelled_synthetic(self) -> None:
        self.assertIn("synthetic", PROTOTYPE.read_text(encoding="utf-8").lower())

    def test_each_view_matches_its_golden(self) -> None:
        for name in VIEWS:
            with self.subTest(view=name):
                self.assertEqual(self.first[name], (GOLDEN / name).read_text(encoding="utf-8"))

    def test_two_runs_are_identical(self) -> None:
        self.assertEqual(self.first, self.second)

    def test_the_chain_links_inventory_trace_and_manual(self) -> None:
        self.assertIn("S2-E06", self.first["inventory.md"])
        self.assertIn("| S2-E06 | Continue | established |", self.first["trace.md"])
        self.assertIn("**“Continue”**", self.first["manual.md"])
        self.assertIn("> **Hole:** this screen has no manual yet.", self.first["manual.md"])


if __name__ == "__main__":
    unittest.main()
