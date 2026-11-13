"""IMP-276 (H17b): the user manual of a prototype, `/prototype --manual`.

The agent writes the prose and cites the inventory with {{S2-E06}}; the generator
injects the element's literal text. A paragraph without citation is refused, the
prose carries no figures, and a screen without manual is a visible hole.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.prototype import extract_inventory
from sentinel.prototype_manual import FINDING_CODES, render_manual, validate_manual

ROOT = Path(__file__).resolve().parent
PROTOTYPE = ROOT / "fixtures" / "synthetic_prototype" / "claims-portal.html"
SKILL = ROOT.parent / ".codex" / "skills" / "sentinel-prototype-manual" / "SKILL.md"
INVENTORY = {"project_id": "P", "prototypes": [{"source": "F-01", "path": "00_raw/claims-portal.html",
                                                **extract_inventory(PROTOTYPE.read_text(encoding="utf-8"))}]}
MANUAL = {
    "prototype": "F-01",
    "screens": [{
        "screen": "S2",
        "purpose": "Sign in to the portal before filing a claim, from {{S2-E01}}.",
        "steps": [{"text": "Type your email in {{S2-E03}}."},
                  {"text": "Type your password in {{S2-E05}} and press {{S2-E06}}."}],
        "notes": ["If you see {{S2-E07}}, check the email and the password and try again.",
                  "When the session ends you see {{JS-06}}"],
    }],
}


def codes(payload: dict) -> set[str]:
    return {f["code"] for f in validate_manual(INVENTORY, payload)["findings"]}


class ValidatorTests(unittest.TestCase):
    def test_valid_manual(self) -> None:
        self.assertEqual(codes(MANUAL), set())

    def test_a_paragraph_without_citation_is_refused(self) -> None:
        payload = copy.deepcopy(MANUAL)
        payload["screens"][0]["steps"].append({"text": "Wait until the portal answers."})
        self.assertEqual(codes(payload), {"paragraph_without_citation"})

    def test_figures_and_unknown_elements(self) -> None:
        payload = copy.deepcopy(MANUAL)
        payload["screens"][0]["notes"] = ["After 3 tries {{S2-E07}} stays."]
        payload["screens"][0]["steps"][0]["text"] = "Press {{S3-E07}}."  # an element of another screen
        self.assertEqual(codes(payload), {"written_figure", "unknown_element"})

    def test_shape_screens_and_duplicates(self) -> None:
        self.assertEqual(codes({"prototype": "F-01", "screens": []}), {"payload_shape"})
        self.assertEqual(codes({"prototype": "F-09", "screens": [{"screen": "S2"}]}), {"unknown_prototype"})
        payload = copy.deepcopy(MANUAL)
        payload["screens"] += [copy.deepcopy(MANUAL["screens"][0]), {"screen": "S9", "purpose": "x {{S9-E01}}"}, {"screen": "S3"}]
        self.assertEqual(codes(payload), {"duplicate_screen", "unknown_screen", "empty_screen"})
        for code in ("payload_shape", "unknown_screen", "written_figure"):
            self.assertIn(code, FINDING_CODES)

    def test_render_injects_the_literal_text_and_marks_holes(self) -> None:
        text = render_manual("P", INVENTORY, {"F-01": MANUAL})
        self.assertIn("2. Type your password in **“Password”** and press **“Continue”**.", text)
        self.assertIn("**“Your session expired. Sign in again.”**", text)
        self.assertIn("### S3 My claims", text)
        self.assertIn("> **Hole:** this screen has no manual yet.", text)
        self.assertIn("Screens without manual: 3.", text)
        self.assertEqual(render_manual("P", INVENTORY, {"F-01": MANUAL}), text)  # deterministic


class SkillTests(unittest.TestCase):
    def test_skill_contract(self) -> None:
        from sentinel.doctor import REQUIRED_CODEX_SKILLS

        self.assertIn("sentinel-prototype-manual", REQUIRED_CODEX_SKILLS)
        text = SKILL.read_text(encoding="utf-8-sig")
        for anchor in ("/prototype PROJECT_ID --manual", "{{S2-E06}}", "## Workflow", "## Manual format", "## Rules",
                       "## Anti-patterns", "Not for", "hole"):
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
        self.view = Path("workspaces") / "P" / "02_requirements" / "prototype" / "manual.md"

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(list(argv))
        return code, out.getvalue()

    def submit(self, payload: dict) -> tuple[int, str]:
        Path("manual.json").write_text(json.dumps(payload), encoding="utf-8")
        return self.cli("prototype", "P", "--manual", "--source", "manual.json")

    def test_submissions_merge_by_screen(self) -> None:
        code, out = self.submit(MANUAL)
        self.assertEqual(code, 0, out)
        self.assertEqual((json.loads(out)["screens_with_manual"], json.loads(out)["screens_without_manual"]), (1, 3))
        second = {"prototype": "F-01", "screens": [{"screen": "S3", "purpose": "Follow your claims in {{S3-E01}}.",
                                                     "steps": [{"text": "Find the claim under {{S3-E02}}."}]}]}
        code, out = self.submit(second)
        self.assertEqual(json.loads(out)["screens_with_manual"], 2)
        text = self.view.read_text(encoding="utf-8")
        self.assertIn("**“Continue”**", text)  # S2 kept
        self.assertIn("**“My claims”**", text)
        self.assertIn("Screens without manual: 2.", text)
        self.assertEqual(self.cli("view", "P", "--artifact", "prototype-manual")[0], 0)

    def test_a_refused_manual_stores_nothing(self) -> None:
        payload = copy.deepcopy(MANUAL)
        payload["screens"][0]["purpose"] = "Sign in to the portal."
        code, out = self.submit(payload)
        self.assertNotEqual(code, 0)
        self.assertIn("paragraph_without_citation", out)
        self.assertFalse(self.view.exists())

    def test_manual_needs_a_source(self) -> None:
        code, out = self.cli("prototype", "P", "--manual")
        self.assertNotEqual(code, 0)
        self.assertIn("--source", out)


if __name__ == "__main__":
    unittest.main()
