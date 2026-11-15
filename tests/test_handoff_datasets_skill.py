"""IMP-196: handoff-datasets skill presence, metadata, and contract anchors."""
from __future__ import annotations

import unittest
from pathlib import Path

from sentinel.doctor import REQUIRED_CODEX_SKILLS

REPO = Path(__file__).resolve().parents[1]
SKILL = "sentinel-handoff-datasets"


def _skill_text() -> str:
    return (REPO / ".codex" / "skills" / SKILL / "SKILL.md").read_text(encoding="utf-8-sig")


class HandoffDatasetsSkillTests(unittest.TestCase):
    def test_registered_in_doctor_required_skills(self):
        self.assertIn(SKILL, REQUIRED_CODEX_SKILLS)

    # IMP-305: metadata and mirror sync are checked for every skill in
    # test_skill_drift_guards and test_skill_render.

    def test_contract_anchors_present(self):
        text = _skill_text()
        for anchor in (
            "## Workflow",
            "## Rules",
            "## Anti-patterns",
            "SYNTHETIC — not evidence",
            "08_context_packs/synthetic",
            ".gitignore",
            "no_synthetic_citation",
            "never cited",
            "local-first",
        ):
            self.assertIn(anchor, text, f"handoff-datasets skill missing contract anchor: {anchor!r}")


if __name__ == "__main__":
    unittest.main()
