"""IMP-316: the command router closes a turn that leaves the user a decision with
one question and a few options, and every surface's copy says so."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER_COPIES = (
    ".codex/skills/sentinel-command-router/SKILL.md",
    ".agents/skills/sentinel-command-router/SKILL.md",
    ".claude/skills/sentinel-command-router/SKILL.md",
    "plugins/ignite-sentinel/skills/sentinel-command-router/SKILL.md",
)


class RouterClosingChoiceTest(unittest.TestCase):
    def test_every_router_copy_has_the_closing_rule(self):
        for rel in ROUTER_COPIES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(copy=rel):
                self.assertIn("## Closing the turn", text)
                self.assertIn("AskUserQuestion", text)
                self.assertIn("never closes a gap", text)

    def test_operating_rules_carry_it(self):
        self.assertIn("2 to 4 options", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn("2 a 4 opciones", (ROOT / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_router_routes_documents_to_the_entry_check(self):
        text = (ROOT / ROUTER_COPIES[0]).read_text(encoding="utf-8")
        description = text.split("---", 2)[1]
        self.assertIn("armá el brief del release 2 con todo esto", description)
        self.assertIn("sentinel-intake-triage", description)
        self.assertIn("use `sentinel-intake-triage` (entry check)", text)
        self.assertIn("Build the options from `next_action`", text)
        self.assertIn(".claude/launch.json", text)


if __name__ == "__main__":
    unittest.main()
