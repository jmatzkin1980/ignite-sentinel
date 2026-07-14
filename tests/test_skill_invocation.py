"""IMP-200 (H8, doc 40 §2): /doctor audit of the human-only skill invocation flag
(`disable-model-invocation: true`). The sanctioned registry must match the skills
actually carrying the flag, and the flag must be coherent across the canonical
source and every mirror.
"""

import tempfile
import unittest
from pathlib import Path

from sentinel.adapters import SKILL_TARGET_DIRS
from sentinel.doctor import EXPECTED_HUMAN_ONLY_SKILLS, skill_invocation_checks

REPO = Path(__file__).resolve().parents[1]

_FLAGGED = '---\nname: {name}\ndescription: "x"\ndisable-model-invocation: true\n---\n\nbody\n'
_PLAIN = '---\nname: {name}\ndescription: "x"\n---\n\nbody\n'


def _write_skill(root: Path, name: str, flagged: bool, mirrors_flagged: bool | None = None) -> None:
    mirrors_flagged = flagged if mirrors_flagged is None else mirrors_flagged
    canonical = root / ".codex" / "skills" / name / "SKILL.md"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text((_FLAGGED if flagged else _PLAIN).format(name=name), encoding="utf-8")
    for target in SKILL_TARGET_DIRS:
        mirror = root / target / name / "SKILL.md"
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text((_FLAGGED if mirrors_flagged else _PLAIN).format(name=name), encoding="utf-8")


class SkillInvocationDoctorCheck(unittest.TestCase):
    def test_repo_passes(self):
        for check in skill_invocation_checks(REPO):
            self.assertEqual(check["status"], "PASS", f"{check['name']}: {check['detail']}")

    def test_privacy_skill_is_the_sanctioned_human_only(self):
        self.assertIn("sentinel-privacy-local-first", EXPECTED_HUMAN_ONLY_SKILLS)

    def test_clean_temp_repo_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_skill(root, "sentinel-privacy-local-first", flagged=True)
            for check in skill_invocation_checks(root):
                self.assertEqual(check["status"], "PASS", f"{check['name']}: {check['detail']}")

    def test_expected_flag_missing_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_skill(root, "sentinel-privacy-local-first", flagged=False)
            statuses = {c["status"] for c in skill_invocation_checks(root)}
            self.assertIn("FAIL", statuses)

    def test_unsanctioned_flag_fails_with_named_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_skill(root, "sentinel-privacy-local-first", flagged=True)
            _write_skill(root, "sentinel-annotate", flagged=True)
            registry = next(c for c in skill_invocation_checks(root) if c["name"].endswith("human-only registry"))
            self.assertEqual(registry["status"], "FAIL")
            self.assertIn("sentinel-annotate", registry["detail"])

    def test_mirror_without_flag_fails_coherence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_skill(root, "sentinel-privacy-local-first", flagged=True, mirrors_flagged=False)
            coherence = next(c for c in skill_invocation_checks(root) if "coherence" in c["name"])
            self.assertEqual(coherence["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
