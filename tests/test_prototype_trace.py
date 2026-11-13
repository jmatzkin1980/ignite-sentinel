"""IMP-275 (H17b): audit and technical support of a prototype screen, `/prototype --trace`.

The agent traces one screen per pass; the runtime validates the trace against the
inventory (IMP-274) and the brief v2 and stores it. Seeded evals cover the defects.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.prototype_trace import FINDING_CODES, STATES, validate_trace

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "evals"))
FIXTURES = ROOT / "fixtures" / "evals" / "prototype_trace"
SKILL = ROOT.parent / ".codex" / "skills" / "sentinel-prototype-trace" / "SKILL.md"
PROTOTYPE = ROOT / "fixtures" / "synthetic_prototype" / "claims-portal.html"
VALID = json.loads((FIXTURES / "valid-trace.json").read_text(encoding="utf-8"))


def codes(payload: dict) -> set[str]:
    result = validate_trace(VALID["inventory"], VALID["brief"], payload, set(VALID["open_gaps"]))
    return {f["code"] for f in result["findings"]}


class EvalTests(unittest.TestCase):
    def test_every_seeded_case_matches(self) -> None:
        import run_prototype_trace_evals

        result = run_prototype_trace_evals.run()
        self.assertGreaterEqual(len(result["cases"]), 10)
        self.assertEqual({c["split"] for c in result["cases"]}, {"tuning", "held_out"})
        for case in result["cases"]:
            with self.subTest(case=case["case"]):
                self.assertTrue(case["ok"], case)

    def test_fixtures_are_labelled_synthetic_and_codes_declared(self) -> None:
        for path in FIXTURES.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data.get("synthetic"), path.name)
            self.assertIn("synthetic fixture", data["brief"])
            for code in data["expected"]:
                self.assertIn(code, FINDING_CODES)


class ValidatorTests(unittest.TestCase):
    def test_valid_summary(self) -> None:
        result = validate_trace(VALID["inventory"], VALID["brief"], VALID["payload"], set(VALID["open_gaps"]))
        self.assertEqual(result["findings"], [])
        summary = result["summary"]
        self.assertEqual((summary["verdict"], summary["levels"]["unsupported"], summary["elements_in_screen"]), ("has_gaps", 1, 7))
        self.assertEqual(set(summary["states"]), set(STATES))

    def test_ids_are_not_figures(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["elements"][1]["rule"] = "see GAP-DESIGN-STATES, C-01, S2-E06 and §3.2"
        self.assertEqual(codes(payload), set())

    def test_supported_verdict(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["elements"] = [e for e in payload["elements"] if e["level"] != "unsupported"]
        result = validate_trace(VALID["inventory"], VALID["brief"], payload, set(VALID["open_gaps"]))
        self.assertEqual(result["summary"]["verdict"], "supported")

    def test_bad_mode_and_state(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["mode"] = "guess"
        payload["states"][1]["status"] = "maybe"
        self.assertEqual(codes(payload), {"bad_mode", "bad_state"})


class SkillTests(unittest.TestCase):
    def test_skill_contract(self) -> None:
        from sentinel.doctor import REQUIRED_CODEX_SKILLS

        self.assertIn("sentinel-prototype-trace", REQUIRED_CODEX_SKILLS)
        text = SKILL.read_text(encoding="utf-8-sig")
        for anchor in ("/prototype PROJECT_ID --inventory", "/prototype PROJECT_ID --trace", "## Workflow", "## Trace format",
                       "## Rules", "## Anti-patterns", "Not for", "executed: false"):
            self.assertIn(anchor, text)


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        Path("claims-portal.html").write_text(PROTOTYPE.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(self.cli("init", "P")[0], 0)
        self.assertEqual(self.cli("ingest", "P", "--source", "claims-portal.html")[0], 0)
        self.assertEqual(self.cli("prototype", "P", "--inventory")[0], 0)
        self.base = Path("workspaces") / "P"
        brief = self.base / "02_requirements" / "project-brief.md"
        brief.write_text(VALID["brief"], encoding="utf-8")
        from sentinel.discovery import render_gaps

        rows = [{"id": g, "lens": "design", "severity": "medium", "status": "OPEN", "description": "synthetic gap",
                 "question": "Which?", "evidence_mention": "§4.1", "origin": "agent", "resolution_note": ""} for g in VALID["open_gaps"]]
        (self.base / "01_discovery" / "gaps.md").write_text(render_gaps("P", rows, "REQ-001", "en"), encoding="utf-8")

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(list(argv))
        return code, out.getvalue()

    def trace(self, payload: dict) -> tuple[int, str]:
        Path("trace.json").write_text(json.dumps(payload), encoding="utf-8")
        return self.cli("prototype", "P", "--trace", "--source", "trace.json")

    def test_a_valid_trace_is_stored_and_viewed(self) -> None:
        code, out = self.trace(VALID["payload"])
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["verdict"], "has_gaps")
        self.assertTrue((self.base / "02_requirements" / "prototype" / "trace" / "F-01-S2.json").is_file())
        view = (self.base / "02_requirements" / "prototype" / "trace.md").read_text(encoding="utf-8")
        self.assertIn("| S2-E06 | Continue | established |", view)
        self.assertEqual(self.cli("view", "P", "--artifact", "prototype-trace")[0], 0)

    def test_a_refused_trace_stores_nothing(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["elements"][1]["element_quote"] = "Go"
        payload["elements"][1]["rule"] = "after 3 attempts"
        code, out = self.trace(payload)
        self.assertNotEqual(code, 0)
        self.assertIn("quote_mismatch", out)
        self.assertIn("written_figure", out)
        self.assertFalse((self.base / "02_requirements" / "prototype" / "trace").exists())

    def test_trace_needs_a_source(self) -> None:
        code, out = self.cli("prototype", "P", "--trace")
        self.assertNotEqual(code, 0)
        self.assertIn("--source", out)


if __name__ == "__main__":
    unittest.main()
