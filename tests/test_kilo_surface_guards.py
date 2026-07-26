"""Anti-drift guards for the handcrafted Kilo agents (IMP-173).

The 7 agents in ``.kilo/agents/`` are maintained by hand (no generator). Before
IMP-173 they were frozen at ~IMP-058: they invited hand-editing/patching of
governed artifacts and knew none of the H1-H5 runtime. These guards (mirroring
the skill mention-checks of IMP-163) fail if a forbidden invitation returns or a
required capability mention is lost, and lean on the ``/doctor`` frontmatter
check.

IMP-233 (H12): this module used to open with "Kilo has no skills — the 7 agents
are its model-facing depth". That premise is false and it is what made the
progressive-disclosure breakage of IMP-231 invisible for so long: Kilo loads
``.agents/skills/`` by default, so the same 24 skills operate there, and 17 of
them have no agent counterpart at all. The agents are Kilo's mode/routing layer,
not a substitute for skills; whether their duplicated depth should be thinned is
an open decision (IMP-234), so these guards stay as they are.
"""

import re
import tempfile
import unittest
from pathlib import Path

from sentinel.adapters import KILO_DEFAULT_SKILL_DIRS, SKILL_TARGET_DIRS
from sentinel.doctor import (
    REQUIRED_KILO_AGENTS,
    _glob_matches,
    kilo_agent_metadata_checks,
    kilo_skill_read_allowlist_check,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / ".kilo" / "agents"
# Matches the verb "patch"/"patching" in prose, not identifiers like `apply_patch`.
FORBIDDEN_INVITATIONS = re.compile(r"manual artifact edits|(?<!\w)patch", re.IGNORECASE)

# Minimum capability mentions each agent must carry so it cannot silently drift
# behind the runtime again. Tokens are stable runtime vocabulary, not prose.
REQUIRED_MENTIONS = {
    "sentinel-discovery": [
        "/annotate", "/challenge", "/scrutinize", "/assume",
        "respondent_profile", "implementability-probe", "uncertainty",
    ],
    "sentinel-sync": ["staleness", "IMP-147", "ASM-", "origin: sync"],
    "sentinel-specs": ["foundation_warnings", "/self-review"],
    "sentinel-backlog": [
        "acceptance_criteria_deltas.md", "foundation_warnings", "/implementation-feedback",
    ],
    "sentinel-health": ["IMP-147", "needs_context", "staleness"],
    "sentinel-maturity": ["development_readiness.json"],
    "sentinel-quality": ["story_gates", "INVEST"],
}


def _text(agent):
    return (AGENTS_DIR / f"{agent}.md").read_text(encoding="utf-8-sig")


class KiloAgentsFreeOfHandEditInvitations(unittest.TestCase):
    def test_no_forbidden_invitations(self):
        for agent in REQUIRED_KILO_AGENTS:
            self.assertIsNone(
                FORBIDDEN_INVITATIONS.search(_text(agent)),
                f"{agent} still invites hand-editing/patching of governed artifacts",
            )

    def test_every_agent_states_governed_mutation(self):
        # The whole surface must, somewhere, forbid hand-editing generated artifacts.
        joined = "\n".join(_text(a).lower() for a in REQUIRED_KILO_AGENTS)
        self.assertIn("never hand-edit", joined)


class KiloAgentsMentionCurrentRuntime(unittest.TestCase):
    def test_required_mentions_present(self):
        for agent, tokens in REQUIRED_MENTIONS.items():
            text = _text(agent)
            for token in tokens:
                self.assertIn(token, text, f"{agent} lost required runtime mention: {token!r}")


class KiloAgentFrontmatterHealthy(unittest.TestCase):
    def test_doctor_reports_all_agents_healthy(self):
        checks = kilo_agent_metadata_checks(REPO_ROOT)
        self.assertEqual(len(checks), len(REQUIRED_KILO_AGENTS))
        unhealthy = [c for c in checks if c["status"] != "PASS"]
        self.assertEqual(unhealthy, [], f"unhealthy Kilo agent frontmatter: {unhealthy}")

    def test_doctor_flags_missing_and_broken_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / ".kilo" / "agents"
            agents.mkdir(parents=True)
            # name/description mismatch → FAIL; missing description → FAIL; others missing → FAIL
            (agents / "sentinel-sync.md").write_text(
                "---\nname: sentinel-sync\n---\nbody\n", encoding="utf-8"
            )
            (agents / "sentinel-health.md").write_text(
                "---\nname: wrong-name\ndescription: x\n---\nbody\n", encoding="utf-8"
            )
            status = {c["name"].split(": ", 1)[1]: c["status"] for c in kilo_agent_metadata_checks(root)}
            self.assertEqual(status["sentinel-sync"], "FAIL")   # missing description
            self.assertEqual(status["sentinel-health"], "FAIL")  # name != file
            self.assertEqual(status["sentinel-backlog"], "FAIL")  # file missing


class KiloReadsItsSkillDiscoveryDirectories(unittest.TestCase):
    """IMP-231 (H12): Kilo discovers skills in `.agents/skills/` (Agent Skills
    compat, loaded by default), but `permissions.file.read` in kilo.jsonc only
    listed `.kilo/**` and `.codex/**` — so the `references/*.md` layer of
    progressive disclosure was outside the read allowlist. These guards keep the
    permission surface tied to the shared discovery constant instead of a
    hand-maintained literal that can silently drift behind a new mirror.
    """

    @staticmethod
    def _read_allowlist(root):
        from sentinel.core.io import parse_json
        from sentinel.doctor import _strip_jsonc

        text = (root / "kilo.jsonc").read_text(encoding="utf-8-sig")
        parsed = parse_json(_strip_jsonc(text))
        return [str(entry) for entry in parsed["permissions"]["file"]["read"]]

    def test_discovery_constant_points_at_real_skill_mirrors(self):
        self.assertTrue(KILO_DEFAULT_SKILL_DIRS, "Kilo must discover skills somewhere")
        for directory in KILO_DEFAULT_SKILL_DIRS:
            self.assertIn(directory, SKILL_TARGET_DIRS, f"{directory} is not a generated skill mirror")
            self.assertTrue((REPO_ROOT / directory).is_dir(), f"missing skill mirror: {directory}")

    def test_every_shipped_skill_file_is_inside_the_read_allowlist(self):
        allow = self._read_allowlist(REPO_ROOT)
        for directory in KILO_DEFAULT_SKILL_DIRS:
            files = [item for item in (REPO_ROOT / directory).rglob("*") if item.is_file()]
            self.assertTrue(files, f"{directory} has no skill files to read")
            for item in files:
                relative = item.relative_to(REPO_ROOT).as_posix()
                self.assertTrue(
                    any(_glob_matches(entry, relative) for entry in allow),
                    f"kilo.jsonc file.read does not cover {relative}",
                )

    def test_permission_glob_matcher_keeps_single_star_inside_a_segment(self):
        deep = ".agents/skills/sentinel-backlog/references/handoff-contracts.md"
        self.assertTrue(_glob_matches(".agents/**", deep))
        self.assertTrue(_glob_matches(".agents/skills/**/references/*.md", deep))
        self.assertFalse(_glob_matches(".agents/*.md", deep))
        self.assertFalse(_glob_matches(".agents/skills/*", deep))
        self.assertFalse(_glob_matches(".codex/**", deep))

    def test_doctor_reports_the_repo_allowlist_healthy(self):
        check = kilo_skill_read_allowlist_check(REPO_ROOT)
        self.assertEqual(check["status"], "PASS", check["detail"])

    def test_doctor_warns_when_the_read_allowlist_drifts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kilo.jsonc").write_text(
                "{\n"
                "  // read allowlist that forgot the skill discovery directory\n"
                '  "permissions": { "file": { "read": [".kilo/**", ".codex/**"] } }\n'
                "}\n",
                encoding="utf-8",
            )
            check = kilo_skill_read_allowlist_check(root)
            self.assertEqual(check["status"], "WARN")
            for directory in KILO_DEFAULT_SKILL_DIRS:
                self.assertIn(directory, check["detail"])

    def test_doctor_warns_when_the_allowlist_stops_short_of_the_reference_layer(self):
        # A top-level-only entry looks like coverage but never reaches
        # `<skill>/references/*.md`, which is exactly what IMP-231 fixes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kilo.jsonc").write_text(
                '{ "permissions": { "file": { "read": [".agents/*.md"] } } }\n',
                encoding="utf-8",
            )
            self.assertEqual(kilo_skill_read_allowlist_check(root)["status"], "WARN")

    def test_doctor_warns_when_kilo_config_is_missing_or_unparseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(kilo_skill_read_allowlist_check(root)["status"], "WARN")
            (root / "kilo.jsonc").write_text("{ not json", encoding="utf-8")
            self.assertEqual(kilo_skill_read_allowlist_check(root)["status"], "WARN")


if __name__ == "__main__":
    unittest.main()
