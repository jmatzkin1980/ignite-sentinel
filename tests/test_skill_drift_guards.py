"""IMP-163: anti-drift guards between canonical skills and the runtime.

The H5 audit found skills silently drifting behind the runtime they describe
(command router knowing 24 of 32 commands, /challenge teaching 3 of 7 registry
techniques, /assume omitting runtime fields). These guards anchor each skill to
the runtime's own source of truth (commands manifest, technique registry,
assumption schema) so that kind of drift fails `verify.ps1` instead of passing
silently.

The original debt ledger (ROUTER_DEBT, CHALLENGE_DEBT, ASSUME_RUNTIME_EXTRA)
was self-cleaning: each entry also asserted the drift was STILL present, so the
content PR fixing a skill had to delete its entry. IMP-164 burned down
CHALLENGE_DEBT and ASSUME_RUNTIME_EXTRA; IMP-167 burned down ROUTER_DEBT.
The ledger is now empty — new deliberate drift must register a new DEBT set
following the same pattern.
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

# IMP-168: every agentic proposal skill carries the same closing spirit block
# (citation rejection loop, severity rubric, project language, focus first).
# The block is repeated inline because skill readers scope to one skill
# directory — a shared references/ file across skills would not resolve.
SPIRIT_HEADER = "## Agentic Spirit (applies to every proposal you author)"
SPIRIT_SKILLS = (
    "sentinel-annotate",
    "sentinel-challenge",
    "sentinel-scrutiny",
    "sentinel-assume",
    "sentinel-compose",
    "sentinel-backlog-refine",
    "sentinel-self-review",
)


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
        for command in sorted(manifest - ROUTER_EXEMPT):
            self.assertIn(f"/{command}", text, f"router skill does not document /{command}")


class ChallengeMentionGuardTests(unittest.TestCase):
    def test_challenge_teaches_every_registry_technique(self):
        text = skill_text("sentinel-challenge")
        for technique in TECHNIQUE_ORDER:
            self.assertIn(technique, text, f"challenge skill does not teach registry technique {technique}")


class AgenticSpiritBlockGuardTests(unittest.TestCase):
    def test_spirit_block_is_identical_across_agentic_skills(self):
        def closing_block(name: str) -> str:
            text = skill_text(name)
            start = text.find(SPIRIT_HEADER)
            self.assertNotEqual(start, -1, f"{name} does not carry the agentic spirit block")
            return text[start:].strip()

        reference = closing_block(SPIRIT_SKILLS[0])
        for name in SPIRIT_SKILLS[1:]:
            self.assertEqual(
                closing_block(name),
                reference,
                f"{name}: agentic spirit block diverged from {SPIRIT_SKILLS[0]} — keep the wording identical in all {len(SPIRIT_SKILLS)} skills",
            )


# IMP-190: coaching posture + anti-patterns are per-skill content (each ladder /
# each anti-pattern list is skill-specific), so unlike the byte-identical spirit
# block above these are minimum-mention guards — every target skill must carry the
# section header, but the rungs/rows differ per skill.
DECISION_LADDER_HEADER = "## Adaptive Decision Ladder"
DECISION_LADDER_SKILLS = (
    "sentinel-maturity",
    "sentinel-health",
    "sentinel-project-brief",
    "sentinel-dashboard",
)
ANTI_PATTERNS_HEADER = "## Anti-patterns"
ANTI_PATTERNS_SKILLS = (
    "sentinel-backlog",
    "sentinel-specs",
    "sentinel-gap-response",
)


class DecisionLadderMentionGuardTests(unittest.TestCase):
    def test_coaching_ladder_present_in_every_decision_skill(self):
        for name in DECISION_LADDER_SKILLS:
            self.assertIn(
                DECISION_LADDER_HEADER,
                skill_text(name),
                f"{name} lost its Adaptive Decision Ladder coaching section (IMP-190)",
            )


class AntiPatternsMentionGuardTests(unittest.TestCase):
    def test_anti_patterns_block_present_in_every_deliverable_skill(self):
        for name in ANTI_PATTERNS_SKILLS:
            self.assertIn(
                ANTI_PATTERNS_HEADER,
                skill_text(name),
                f"{name} lost its Anti-patterns block (IMP-190)",
            )


class AssumeContractGuardTests(unittest.TestCase):
    def test_assume_documents_every_contract_field(self):
        text = skill_text("sentinel-assume")
        schema = json.loads((REPO / "sentinel" / "schemas" / "assumption.schema.json").read_text(encoding="utf-8"))
        schema_fields = set(schema["properties"]["assumptions"]["items"]["properties"])
        for field in sorted(schema_fields):
            self.assertIn(field, text, f"assume skill does not document schema field '{field}'")
