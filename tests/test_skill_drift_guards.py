"""IMP-163: anti-drift guards between canonical skills and the runtime.

The H5 audit found skills silently drifting behind the runtime they describe
(command router knowing 24 of 32 commands, /challenge teaching 3 of 7 registry
techniques, /assume omitting runtime fields). These guards anchor each skill to
the runtime's own source of truth (commands manifest, technique registry,
assumption schema) so that kind of drift fails `verify.ps1` instead of passing
silently.

Known, deliberate drift is registered below as explicit DEBT sets. The debt
assertions are self-cleaning: they also assert the entry is STILL missing, so
the content PR that fixes a skill must delete the corresponding debt entry —
the ledger can only shrink. IMP-164 burned down CHALLENGE_DEBT and
ASSUME_RUNTIME_EXTRA; ROUTER_DEBT remains for IMP-167.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sentinel.adapters import manifest_command_names
from sentinel.doctor import skill_metadata_checks
from sentinel.technique_registry import TECHNIQUE_ORDER

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / ".codex" / "skills"

# The generic entry point is documented by the router as the `sentinel
# /COMMAND` prefix form, not as a literal `/sentinel` slash command.
ROUTER_EXEMPT = {"sentinel"}

# Commands the router does not document yet; burned down by IMP-167.
ROUTER_DEBT = {
    "annotate",
    "challenge",
    "scrutinize",
    "self-review",
    "assume",
    "backlog-status",
    "refine-backlog",
    "story-status",
}


def skill_text(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8-sig")


class SkillMetadataChecksTests(unittest.TestCase):
    def test_repo_skills_all_pass_metadata_checks(self):
        for check in skill_metadata_checks(REPO):
            self.assertEqual(check["status"], "PASS", f"{check['name']}: {check.get('detail', '')}")

    def test_broken_frontmatter_is_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill_dir = root / ".codex" / "skills" / "sentinel-annotate"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# Sentinel Annotate\n\nBody without frontmatter.\n", encoding="utf-8")
            checks = {check["name"]: check for check in skill_metadata_checks(root)}
            broken = checks["Codex skill metadata: sentinel-annotate"]
            self.assertEqual(broken["status"], "FAIL")
            self.assertIn("frontmatter", broken["detail"])

    def test_name_directory_mismatch_is_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill_dir = root / ".codex" / "skills" / "sentinel-annotate"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                '---\nname: sentinel-other\ndescription: "Valid description."\n---\n\n# Body\n',
                encoding="utf-8",
            )
            checks = {check["name"]: check for check in skill_metadata_checks(root)}
            self.assertEqual(checks["Codex skill metadata: sentinel-annotate"]["status"], "FAIL")


class RouterMentionGuardTests(unittest.TestCase):
    def test_router_documents_every_manifest_command(self):
        text = skill_text("sentinel-command-router")
        manifest = set(manifest_command_names())
        self.assertLessEqual(ROUTER_DEBT, manifest, "debt entries must be real manifest commands")
        for command in sorted(manifest - ROUTER_EXEMPT):
            token = f"/{command}"
            if command in ROUTER_DEBT:
                self.assertNotIn(token, text, f"{token} is now documented: delete it from ROUTER_DEBT")
            else:
                self.assertIn(token, text, f"router skill does not document {token}")


class ChallengeMentionGuardTests(unittest.TestCase):
    def test_challenge_teaches_every_registry_technique(self):
        text = skill_text("sentinel-challenge")
        for technique in TECHNIQUE_ORDER:
            self.assertIn(technique, text, f"challenge skill does not teach registry technique {technique}")


class AssumeContractGuardTests(unittest.TestCase):
    def test_assume_documents_every_contract_field(self):
        text = skill_text("sentinel-assume")
        schema = json.loads((REPO / "sentinel" / "schemas" / "assumption.schema.json").read_text(encoding="utf-8"))
        schema_fields = set(schema["properties"]["assumptions"]["items"]["properties"])
        for field in sorted(schema_fields):
            self.assertIn(field, text, f"assume skill does not document schema field '{field}'")
