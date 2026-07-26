"""IMP-232 (H12): enforce the Agent Skills standard over the canonical skills.

Before this guard the only guarantees over the 24 skills were byte identity
between mirrors (`skills_out_of_sync`) and name/description sanity
(`skill_metadata_checks`). Nothing checked the limits of the standard itself or
which frontmatter fields are legitimate, so the skills complied by discipline
rather than by enforcement — and a vendor field that only works on one surface
could enter without anyone noticing. The guard freezes today's state: all 24
already pass, so it changes no skill content.
"""

import tempfile
import unittest
from pathlib import Path

from sentinel.doctor import (
    AGENT_SKILL_STANDARD_FIELDS,
    AGENT_SKILL_VENDOR_FIELDS,
    MAX_SKILL_DESCRIPTION_LENGTH,
    MAX_SKILL_LINES,
    MAX_SKILL_NAME_LENGTH,
    skill_invocation_checks,
    skill_spec_compliance_check,
    skill_spec_violations,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SKILLS = REPO_ROOT / ".codex" / "skills"


def _skill_repo(tmp: str, name: str, frontmatter: str, body: str = "Do the thing.\n") -> Path:
    """Materialize a one-skill repo so a single spec rule can be violated alone."""
    root = Path(tmp)
    directory = root / ".codex" / "skills" / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")
    return root


class CanonicalSkillsMeetTheStandard(unittest.TestCase):
    def test_no_violations_in_the_repo(self):
        self.assertEqual(skill_spec_violations(REPO_ROOT), [])

    def test_doctor_passes_and_counts_every_skill(self):
        check = skill_spec_compliance_check(REPO_ROOT)
        self.assertEqual(check["status"], "PASS", check["detail"])
        total = len([item for item in CANONICAL_SKILLS.iterdir() if item.is_dir()])
        self.assertIn(f"{total} skills valid", check["detail"])

    def test_every_frontmatter_field_in_use_is_declared(self):
        from sentinel.core.markdown import parse_frontmatter

        declared = AGENT_SKILL_STANDARD_FIELDS | set(AGENT_SKILL_VENDOR_FIELDS)
        for directory in sorted(item for item in CANONICAL_SKILLS.iterdir() if item.is_dir()):
            fields = set(parse_frontmatter((directory / "SKILL.md").read_text(encoding="utf-8-sig")))
            self.assertLessEqual(fields, declared, f"{directory.name} carries an undeclared field")


class VendorFieldsDeclareTheirSurface(unittest.TestCase):
    def test_disable_model_invocation_is_registered_as_claude_only(self):
        # It is not part of the standard: it is a Claude Code extension, and the
        # registry must say so, because the mirrors ship it to all three surfaces.
        self.assertNotIn("disable-model-invocation", AGENT_SKILL_STANDARD_FIELDS)
        surface = AGENT_SKILL_VENDOR_FIELDS["disable-model-invocation"]
        self.assertIn("Claude Code", surface)
        self.assertIn("no-op", surface)

    def test_doctor_states_the_claude_only_reach_of_the_human_only_policy(self):
        registry = next(
            check for check in skill_invocation_checks(REPO_ROOT) if check["name"].endswith("human-only registry")
        )
        self.assertEqual(registry["status"], "PASS", registry["detail"])
        self.assertIn("Claude Code", registry["detail"])
        self.assertIn("no-op", registry["detail"])


class SpecViolationsAreCaught(unittest.TestCase):
    def _violations(self, **kwargs) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            return skill_spec_violations(_skill_repo(tmp, **kwargs))

    def test_undeclared_frontmatter_field(self):
        violations = self._violations(
            name="sentinel-demo",
            frontmatter="name: sentinel-demo\ndescription: A demo skill.\nmodel: haiku",
        )
        self.assertEqual(len(violations), 1, violations)
        self.assertIn("undeclared frontmatter field(s): model", violations[0])

    def test_declared_vendor_field_is_accepted(self):
        self.assertEqual(
            self._violations(
                name="sentinel-demo",
                frontmatter="name: sentinel-demo\ndescription: A demo skill.\ndisable-model-invocation: true",
            ),
            [],
        )

    def test_standard_optional_fields_are_accepted(self):
        self.assertEqual(
            self._violations(
                name="sentinel-demo",
                frontmatter="name: sentinel-demo\ndescription: A demo skill.\nlicense: MIT",
            ),
            [],
        )

    def test_name_format(self):
        for bad in ("Sentinel-Demo", "sentinel--demo", "-sentinel-demo", "sentinel_demo"):
            violations = self._violations(
                name="sentinel-demo", frontmatter=f"name: {bad}\ndescription: A demo skill."
            )
            self.assertTrue(
                any("not lowercase hyphen-separated" in item for item in violations),
                f"accepted invalid name {bad!r}: {violations}",
            )

    def test_name_length(self):
        long_name = "a" * (MAX_SKILL_NAME_LENGTH + 1)
        violations = self._violations(
            name="sentinel-demo", frontmatter=f"name: {long_name}\ndescription: A demo skill."
        )
        self.assertTrue(any("name is 65 chars" in item for item in violations), violations)

    def test_description_length(self):
        violations = self._violations(
            name="sentinel-demo",
            frontmatter="name: sentinel-demo\ndescription: " + "x" * (MAX_SKILL_DESCRIPTION_LENGTH + 1),
        )
        self.assertTrue(any("description is 1025 chars" in item for item in violations), violations)

    def test_skill_line_budget(self):
        violations = self._violations(
            name="sentinel-demo",
            frontmatter="name: sentinel-demo\ndescription: A demo skill.",
            body="line\n" * (MAX_SKILL_LINES + 1),
        )
        self.assertTrue(any("split into references/" in item for item in violations), violations)

    def test_references_may_not_nest_beyond_one_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _skill_repo(
                tmp, name="sentinel-demo", frontmatter="name: sentinel-demo\ndescription: A demo skill."
            )
            skill = root / ".codex" / "skills" / "sentinel-demo"
            (skill / "references").mkdir()
            (skill / "references" / "shallow.md").write_text("ok\n", encoding="utf-8")
            self.assertEqual(skill_spec_violations(root), [], "one reference level must be allowed")

            deep = skill / "references" / "deeper"
            deep.mkdir()
            (deep / "buried.md").write_text("too far\n", encoding="utf-8")
            violations = skill_spec_violations(root)
            self.assertTrue(any("nests deeper than one reference level" in item for item in violations), violations)

    def test_missing_skill_file_and_missing_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex" / "skills" / "sentinel-demo").mkdir(parents=True)
            self.assertEqual(skill_spec_violations(root), ["sentinel-demo: SKILL.md missing"])
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(skill_spec_violations(Path(tmp)), [".codex/skills: missing"])

    def test_doctor_fails_and_names_the_offending_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _skill_repo(
                tmp, name="sentinel-demo", frontmatter="name: sentinel-demo\ndescription: A demo.\nmodel: haiku"
            )
            check = skill_spec_compliance_check(root)
            self.assertEqual(check["status"], "FAIL")
            self.assertIn("sentinel-demo", check["detail"])
            self.assertIn("model", check["detail"])


if __name__ == "__main__":
    unittest.main()
