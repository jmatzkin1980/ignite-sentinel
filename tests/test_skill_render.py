"""IMP-278: per-surface skill rendering (one portable body, one overlay line).

Every skill body is written once, in `.codex/skills/`. A surface overlay may
change only the line that invokes the runtime: the clone runs
``python -m sentinel``, a plugin runs its own ``launcher.py``. The clone mirrors
stay byte-identical to the source.
"""

from __future__ import annotations

import difflib
import tempfile
import unittest
from pathlib import Path

from sentinel.adapters import (
    CANONICAL_SKILLS_DIR,
    RUNTIME_INVOCATION,
    SKILL_OVERLAYS,
    render_skill,
    render_skills,
    skill_files,
    skills_out_of_sync,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = "claude-plugin"


class OverlayTests(unittest.TestCase):
    def test_clone_overlay_is_the_identity(self) -> None:
        for item in skill_files(REPO_ROOT):
            with self.subTest(path=item.name):
                self.assertEqual(render_skill(item.read_bytes(), "clone", item.suffix), item.read_bytes())

    def test_clone_mirrors_stay_byte_identical(self) -> None:
        self.assertEqual(skills_out_of_sync(REPO_ROOT), [])

    def test_plugin_overlay_touches_only_the_invocation(self) -> None:
        plugin = SKILL_OVERLAYS[PLUGIN]
        base = REPO_ROOT / CANONICAL_SKILLS_DIR
        rendered = render_skills(REPO_ROOT, PLUGIN)
        touched = 0
        for item in skill_files(REPO_ROOT):
            relative = item.relative_to(base).as_posix()
            source = item.read_text(encoding="utf-8").splitlines()
            output = rendered[relative].decode("utf-8").splitlines()
            self.assertEqual(len(source), len(output), relative)
            for before, after in zip(source, output):
                if before != after:
                    touched += 1
                    self.assertIn(RUNTIME_INVOCATION, before, relative)
                    self.assertNotIn(RUNTIME_INVOCATION + " ", after.replace(plugin, ""), relative)
                    self.assertEqual(after.replace(plugin, RUNTIME_INVOCATION), before, relative)
        self.assertGreater(touched, 0, "no skill invokes the runtime: the overlay is untested")

    def test_plugin_overlay_reaches_every_invocation(self) -> None:
        for relative, content in render_skills(REPO_ROOT, PLUGIN).items():
            with self.subTest(path=relative):
                text = content.decode("utf-8")
                self.assertNotRegex(text, r"python -m sentinel(?![\w.])")

    def test_other_modules_are_not_rewritten(self) -> None:
        text = b"Run `python -m sentinel.adapters` then `python -m sentinel /doctor`.\n"
        output = render_skill(text, PLUGIN, ".md").decode("utf-8")
        self.assertIn("python -m sentinel.adapters", output)
        self.assertIn(SKILL_OVERLAYS[PLUGIN] + " /doctor", output)

    def test_non_text_files_pass_through(self) -> None:
        blob = b"\x89PNG python -m sentinel"
        self.assertEqual(render_skill(blob, PLUGIN, ".png"), blob)

    def test_unknown_surface_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            render_skill(b"x", "vscode", ".md")

    def test_source_never_carries_an_overlay_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / CANONICAL_SKILLS_DIR / "sentinel-demo"
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(f"Run `{SKILL_OVERLAYS[PLUGIN]} /doctor`.\n", encoding="utf-8")
            issues = skills_out_of_sync(root)
        self.assertTrue(any("overlay invocation" in item for item in issues), issues)


if __name__ == "__main__":
    unittest.main()
