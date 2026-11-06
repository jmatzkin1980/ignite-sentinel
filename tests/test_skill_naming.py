"""IMP-277: skill naming convention and description best practices.

Every canonical skill is named ``sentinel-<object>[-<action>]`` (kebab-case,
English, no surface or vendor names), its description opens with the trigger
("Use when…", "Use on…" or "Use before…") and states when NOT to use it
("Not for…" / "Not needed…"), so an agent can choose between neighbouring skills.
In a plugin the skills are namespaced (``ignite-sentinel:sentinel-views``); the
name stays identical to the clone.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel.adapters import skills_out_of_sync
from sentinel.doctor import skill_naming_check, skill_naming_violations

REPO_ROOT = Path(__file__).resolve().parents[1]
GOOD = 'description: "Use when testing the naming rules. Not for real work (use sentinel-discovery)."'


def _repo(tmp: str, name: str, description: str = GOOD) -> Path:
    root = Path(tmp)
    directory = root / ".codex" / "skills" / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(f"---\nname: {name}\n{description}\n---\n\nBody.\n", encoding="utf-8")
    return root


class NamingConventionTests(unittest.TestCase):
    def test_repo_skills_follow_the_convention(self) -> None:
        self.assertEqual(skill_naming_violations(REPO_ROOT), [])
        self.assertEqual(skill_naming_check(REPO_ROOT)["status"], "PASS")

    def test_good_skill_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(skill_naming_violations(_repo(tmp, "sentinel-demo-check")), [])

    def test_prefix_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            violations = skill_naming_violations(_repo(tmp, "demo-check"))
        self.assertTrue(any("sentinel-" in item for item in violations), violations)

    def test_surface_and_vendor_names_are_rejected(self) -> None:
        for name in ("sentinel-claude-views", "sentinel-codex-sync", "sentinel-kilo-brief", "sentinel-copilot"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                violations = skill_naming_violations(_repo(tmp, name))
                self.assertTrue(any("surface" in item for item in violations), violations)

    def test_description_must_open_with_a_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            violations = skill_naming_violations(_repo(tmp, "sentinel-demo", 'description: "Register things. Not for other things."'))
        self.assertTrue(any("Use when" in item for item in violations), violations)

    def test_description_must_say_when_not_to_use_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            violations = skill_naming_violations(_repo(tmp, "sentinel-demo", 'description: "Use when doing demos."'))
        self.assertTrue(any("Not for" in item for item in violations), violations)

    def test_failure_is_reported_by_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = skill_naming_check(_repo(tmp, "demo"))
        self.assertEqual(result["status"], "FAIL")


class RenameTests(unittest.TestCase):
    def test_views_skill_replaces_dashboard_everywhere(self) -> None:
        for surface in (".codex/skills", ".agents/skills", ".claude/skills"):
            with self.subTest(surface=surface):
                self.assertTrue((REPO_ROOT / surface / "sentinel-views" / "SKILL.md").exists())
                self.assertFalse((REPO_ROOT / surface / "sentinel-dashboard").exists())

    def test_no_live_reference_to_the_old_name(self) -> None:
        roots = ["sentinel", "tests", "user_guide", ".codex", ".agents", ".claude/skills", ".claude/commands", ".kilo"]
        files = ["README.md", "AGENTS.md", "CLAUDE.md", "MAINTAINERS.md"]
        offenders = []
        for root in roots:
            for path in (REPO_ROOT / root).rglob("*"):
                if path.is_file() and path.suffix in {".md", ".py", ".json", ".txt"} and path.name != "test_skill_naming.py":
                    if "sentinel-dashboard" in path.read_text(encoding="utf-8", errors="ignore"):
                        offenders.append(path.relative_to(REPO_ROOT).as_posix())
        for name in files:
            if "sentinel-dashboard" in (REPO_ROOT / name).read_text(encoding="utf-8"):
                offenders.append(name)
        self.assertEqual(offenders, [])

    def test_stale_mirror_skill_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, "sentinel-demo")
            for target in (".agents/skills", ".claude/skills"):
                mirror = root / target / "sentinel-demo"
                mirror.mkdir(parents=True)
                (mirror / "SKILL.md").write_bytes((root / ".codex/skills/sentinel-demo/SKILL.md").read_bytes())
            stale = root / ".claude/skills" / "sentinel-old"
            stale.mkdir()
            (stale / "SKILL.md").write_text("---\nname: sentinel-old\n---\n", encoding="utf-8")
            issues = skills_out_of_sync(root)
        self.assertTrue(any("sentinel-old" in item for item in issues), issues)


if __name__ == "__main__":
    unittest.main()
