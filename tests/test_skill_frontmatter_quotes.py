"""IMP-400 fix: a double-quoted YAML description must not hold an unescaped double quote."""
from __future__ import annotations

import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / ".codex" / "skills"


def bad_description(text: str) -> str | None:
    """Return a problem for a double-quoted `description:` scalar, else None."""
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        if line.startswith("description:"):
            value = line[len("description:"):].strip()
            if not value.startswith('"'):
                return None
            if not value.endswith('"') or len(value) < 2:
                return "unterminated double-quoted scalar"
            inner, i = value[1:-1], 0
            while i < len(inner):
                if inner[i] == "\\":
                    i += 2
                    continue
                if inner[i] == '"':
                    return f"unescaped double quote at {i}"
                i += 1
    return None


class SkillDescriptionsAreValidYaml(unittest.TestCase):
    def test_no_unescaped_double_quote_in_any_description(self):
        skills = sorted(SKILLS.glob("*/SKILL.md"))
        self.assertTrue(skills)
        for path in skills:
            with self.subTest(skill=path.parent.name):
                self.assertIsNone(bad_description(path.read_text(encoding="utf-8")))

    def test_the_check_catches_the_broken_shape(self):
        broken = '---\nname: x\ndescription: "say "hola" now"\n---\n'
        self.assertIsNotNone(bad_description(broken))
        self.assertIsNone(bad_description('---\nname: x\ndescription: "say \\"hola\\" now"\n---\n'))
        self.assertIsNone(bad_description("---\nname: x\ndescription: \"say 'hola' now\"\n---\n"))


if __name__ == "__main__":
    unittest.main()
