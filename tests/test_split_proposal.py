"""IMP-265 (H17a): /split --propose and the sentinel-release-split skill.

The agent writes the series proposal; the runtime validates structure, anchors
to the brief v2 and the release contracts, and stores a valid proposal in
`02_requirements/series/proposal.json`. Nothing is compiled.
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
from sentinel.release_split_model import RELEASE_TYPES
from sentinel.split_proposal import FINDING_CODES, STRENGTHS, SplitProposalError, validate_proposal

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "evals"))
FIXTURES = ROOT / "fixtures" / "evals" / "split_proposal"
SCHEMA = ROOT.parent / "sentinel" / "schemas" / "release_split_proposal.schema.json"
SKILL = ROOT.parent / ".codex" / "skills" / "sentinel-release-split" / "SKILL.md"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


VALID = fixture("valid-proposal")


def codes(payload: dict, brief: str | None = None, gaps: list[str] | None = None) -> set[str]:
    result = validate_proposal(brief or VALID["brief"], payload, set(VALID["open_gaps"] if gaps is None else gaps))
    return {f["code"] for f in result["findings"]}


class EvalTests(unittest.TestCase):
    def test_every_seeded_case_matches(self) -> None:
        import run_split_proposal_evals

        result = run_split_proposal_evals.run()
        self.assertGreaterEqual(len(result["cases"]), 10)
        self.assertEqual({c["split"] for c in result["cases"]}, {"tuning", "held_out"})
        for case in result["cases"]:
            with self.subTest(case=case["case"]):
                self.assertTrue(case["ok"], case)

    def test_fixtures_are_labelled_synthetic(self) -> None:
        for path in FIXTURES.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data.get("synthetic"), path.name)
            self.assertIn("synthetic fixture", data["brief"])


class ValidatorTests(unittest.TestCase):
    def test_valid_proposal(self) -> None:
        self.assertEqual(codes(VALID["payload"]), set())

    def test_every_code_is_declared(self) -> None:
        for name in [p.stem for p in FIXTURES.glob("*.json")]:
            for code in fixture(name)["expected"]:
                self.assertIn(code, FINDING_CODES)

    def test_v1_brief_is_rejected(self) -> None:
        with self.assertRaises(SplitProposalError) as caught:
            validate_proposal("# Project Brief\n\n## 1. Identidad\n\n- x\n", VALID["payload"])
        self.assertIn("A43", str(caught.exception))

    def test_criteria_rules(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["criteria"] = [c for c in payload["criteria"] if c["id"] != "C1"]
        self.assertIn("criteria_without_value", codes(payload))
        payload["criteria"][0]["id"] = "C99"
        self.assertIn("unknown_criterion", codes(payload))

    def test_release_criteria_must_be_written_first(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["releases"][1]["criteria"] = ["C7"]
        self.assertIn("criterion_not_written", codes(payload))

    def test_pattern_rules(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["releases"][1]["pattern"] = "P24"
        self.assertIn("pattern_not_a_cut", codes(payload))
        payload["releases"][1]["pattern"] = "P99"
        self.assertIn("unknown_pattern", codes(payload))

    def test_contains_must_be_anchored(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["releases"][1]["contains"] = [{"item": "C-77"}]
        self.assertIn("contains_without_source", codes(payload))

    def test_interleaved_needs_its_id_and_subtype(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["releases"].append({"id": "r5", "name": "x", "type": "interleaved", "wave": 1, "pattern": "P2",
                                    "criteria": ["C1"], "goal": "g", "contains": [{"item": "C-04"}]})
        self.assertIn("interleave_contract", codes(payload))

    def test_inheritance_of_an_unknown_gap(self) -> None:
        self.assertIn("inheritance_unknown_gap", codes(VALID["payload"], gaps=[]))


class SchemaDriftGuard(unittest.TestCase):
    """release_split_proposal.schema.json against validate_proposal."""

    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.release = self.schema["properties"]["releases"]["items"]

    def test_required(self) -> None:
        self.assertEqual(set(self.schema["required"]), {"core", "criteria", "releases"})
        self.assertEqual(set(self.release["required"]), {"id", "name", "type", "pattern", "goal"})

    def test_enums(self) -> None:
        self.assertEqual(set(self.release["properties"]["type"]["enum"]), RELEASE_TYPES)
        self.assertEqual(set(self.schema["$defs"]["edge"]["properties"]["strength"]["enum"]), set(STRENGTHS))
        spike = self.release["properties"]["spike"]["properties"]["questions"]
        self.assertEqual((spike["minItems"], spike["maxItems"]), (1, 3))


class SkillTests(unittest.TestCase):
    def test_skill_contract(self) -> None:
        from sentinel.doctor import REQUIRED_CODEX_SKILLS

        self.assertIn("sentinel-release-split", REQUIRED_CODEX_SKILLS)
        text = SKILL.read_text(encoding="utf-8-sig")
        for anchor in ("release_split_model.json", "/split PROJECT_ID --assess", "/split PROJECT_ID --propose",
                       "## Workflow", "## Proposal format", "## Rules", "## Anti-patterns", "Not for"):
            self.assertIn(anchor, text)


class ApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "P"]), 0)
        self.base = Path("workspaces") / "P"
        brief = self.base / "02_requirements" / "project-brief.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text(VALID["brief"], encoding="utf-8")
        from sentinel.discovery import parse_gap_rows, render_gaps

        rows = [{"id": g, "lens": "business", "severity": "high", "status": "OPEN", "description": "synthetic gap",
                 "question": "Which?", "evidence_mention": "§6.1", "origin": "agent", "resolution_note": ""}
                for g in VALID["open_gaps"]]
        gaps = self.base / "01_discovery" / "gaps.md"
        gaps.parent.mkdir(parents=True, exist_ok=True)
        gaps.write_text(render_gaps("P", rows, "REQ-001", "en"), encoding="utf-8")
        self.assertEqual({g["id"].strip("`") for g in parse_gap_rows(gaps.read_text(encoding="utf-8"))} & set(VALID["open_gaps"]),
                         set(VALID["open_gaps"]))

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def run_cli(self, payload: dict) -> tuple[int, str]:
        path = Path("proposal.json")
        path.write_text(json.dumps(payload), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["split", "P", "--propose", "--source", str(path)])
        return code, out.getvalue() + err.getvalue()

    def test_valid_proposal_is_stored(self) -> None:
        code, out = self.run_cli(VALID["payload"])
        self.assertEqual(code, 0, out)
        stored = json.loads((self.base / "02_requirements" / "series" / "proposal.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["status"], "proposal")
        self.assertEqual([r["id"] for r in stored["summary"]["releases"]], ["r0", "r1", "r2", "r3"])
        self.assertTrue(stored["brief_sha256"])
        self.assertTrue((self.base / "01_discovery" / "split_assessment.json").exists())  # assessed before proposing

    def test_refused_proposal_reports_every_reason_and_stores_nothing(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["releases"][2]["contains"] = []
        payload["criteria"][1]["anchor"]["quote"] = "not in the brief"
        code, out = self.run_cli(payload)
        self.assertNotEqual(code, 0)
        self.assertIn("empty_release", out)
        self.assertIn("criterion_without_source", out)
        self.assertFalse((self.base / "02_requirements" / "series" / "proposal.json").exists())

    def test_propose_needs_a_source(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            self.assertNotEqual(main(["split", "P", "--propose"]), 0)


if __name__ == "__main__":
    unittest.main()
