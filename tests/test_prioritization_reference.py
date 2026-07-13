"""IMP-195: prioritization-frameworks reference presence, linkage, and mirroring."""
from __future__ import annotations

import unittest
from pathlib import Path

from sentinel.adapters import skills_out_of_sync

REPO = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO / ".codex" / "skills" / "sentinel-backlog"
REFERENCE = SKILL_DIR / "references" / "prioritization-frameworks.md"


class PrioritizationReferenceTests(unittest.TestCase):
    def test_reference_exists(self):
        self.assertTrue(REFERENCE.exists(), "prioritization-frameworks.md missing")

    def test_reference_covers_the_named_frameworks(self):
        text = REFERENCE.read_text(encoding="utf-8-sig")
        for framework in ("MoSCoW", "Kano", "RICE", "ICE", "Opportunity Scoring"):
            self.assertIn(framework, text, f"reference missing framework: {framework!r}")

    def test_reference_is_coaching_not_a_mandate(self):
        text = REFERENCE.read_text(encoding="utf-8-sig")
        # Coaching posture (IMP-190): the BA chooses, and inputs must rest on evidence.
        self.assertIn("The BA chooses", text)
        self.assertIn("evidence", text)

    def test_skill_links_the_reference(self):
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8-sig")
        self.assertIn("references/prioritization-frameworks.md", skill)

    def test_mirrors_in_sync(self):
        self.assertEqual(skills_out_of_sync(REPO), [])


if __name__ == "__main__":
    unittest.main()
