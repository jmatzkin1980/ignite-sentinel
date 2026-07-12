"""IMP-193: intake-triage skill presence, metadata, and contract anchors."""
from __future__ import annotations

import unittest
from pathlib import Path

from sentinel.adapters import skills_out_of_sync
from sentinel.doctor import REQUIRED_CODEX_SKILLS, skill_metadata_checks

REPO = Path(__file__).resolve().parents[1]
SKILL = "sentinel-intake-triage"


def _skill_text() -> str:
    return (REPO / ".codex" / "skills" / SKILL / "SKILL.md").read_text(encoding="utf-8-sig")


class IntakeTriageSkillTests(unittest.TestCase):
    def test_registered_in_doctor_required_skills(self):
        self.assertIn(SKILL, REQUIRED_CODEX_SKILLS)

    def test_metadata_passes(self):
        checks = {c["name"]: c for c in skill_metadata_checks(REPO)}
        entry = checks[f"Codex skill metadata: {SKILL}"]
        self.assertEqual(entry["status"], "PASS", entry.get("detail", ""))

    def test_mirrors_in_sync(self):
        self.assertEqual(skills_out_of_sync(REPO), [])

    def test_contract_anchors_present(self):
        text = _skill_text()
        for anchor in (
            "## Workflow",
            "## Rules",
            "## Anti-patterns",
            "Cite-or-silent",
            "Propose, never decide",
            "/init",
            "/ingest",
            "out-of-scope",
        ):
            self.assertIn(anchor, text, f"intake-triage skill missing contract anchor: {anchor!r}")


if __name__ == "__main__":
    unittest.main()
