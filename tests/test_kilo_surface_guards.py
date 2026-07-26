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
    kilo_command_allowlist_check,
    kilo_config_schema_check,
    kilo_governed_deny_check,
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


class KiloSkillDiscoveryDirectories(unittest.TestCase):
    """The directories Kilo loads skills from must be real generated mirrors.

    IMP-231 tied this to a `permissions.file.read` allowlist in kilo.jsonc;
    IMP-235 removed that tie because the key does not exist in Kilo's schema, so
    no allowlist ever applied and the reference layer loads without one
    (confirmed live on Kilo Code 7.4.16, doc 45 §3.2). What survives is the part
    that was always true: the constant must point at directories that exist and
    are generated mirrors, so adding a mirror cannot silently point nowhere.
    """

    def test_discovery_constant_points_at_real_skill_mirrors(self):
        self.assertTrue(KILO_DEFAULT_SKILL_DIRS, "Kilo must discover skills somewhere")
        for directory in KILO_DEFAULT_SKILL_DIRS:
            self.assertIn(directory, SKILL_TARGET_DIRS, f"{directory} is not a generated skill mirror")
            self.assertTrue((REPO_ROOT / directory).is_dir(), f"missing skill mirror: {directory}")

    def test_the_reference_layer_actually_ships(self):
        # Layer 3 of progressive disclosure has to exist for Kilo to open it.
        references = [
            item
            for directory in KILO_DEFAULT_SKILL_DIRS
            for item in (REPO_ROOT / directory).rglob("references/*.md")
        ]
        self.assertTrue(references, "no skill reference files shipped in the Kilo discovery dirs")


class PermissionGlobMatcher(unittest.TestCase):
    def test_path_semantics_keep_single_star_inside_a_segment(self):
        deep = ".agents/skills/sentinel-backlog/references/handoff-contracts.md"
        self.assertTrue(_glob_matches(".agents/**", deep))
        self.assertTrue(_glob_matches(".agents/skills/**/references/*.md", deep))
        self.assertFalse(_glob_matches(".agents/*.md", deep))
        self.assertFalse(_glob_matches(".agents/skills/*", deep))
        self.assertFalse(_glob_matches(".codex/**", deep))

    def test_command_semantics_let_a_single_star_cross_slashes(self):
        # IMP-235: `permission.bash` patterns match a command line, where `/` is
        # an ordinary character. Under path semantics this pattern would miss.
        command = "python -m sentinel /doctor PROJECT_ID"
        self.assertTrue(_glob_matches("python -m sentinel *", command, path_semantics=False))
        self.assertFalse(_glob_matches("python -m sentinel *", command))
        self.assertFalse(_glob_matches("python -m other *", command, path_semantics=False))


class KiloConfigMatchesThePublishedSchema(unittest.TestCase):
    """IMP-235 (H12): the guard that would have caught the original defect.

    `kilo.jsonc` carried a top-level `permissions` block from 2026-06-03 to
    2026-07-26. Kilo discarded it wholesale (`Unrecognized key: permissions`)
    while `/doctor` reported the surface healthy, because every check validated
    the shape we had invented instead of the one Kilo publishes.
    """

    @staticmethod
    def _write(root, body):
        (root / "kilo.jsonc").write_text(body, encoding="utf-8")

    def test_repo_config_conforms(self):
        check = kilo_config_schema_check(REPO_ROOT)
        self.assertEqual(check["status"], "PASS", check["detail"])

    def test_the_historical_defect_is_now_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(
                root,
                "{\n"
                '  "$schema": "https://app.kilo.ai/config.json",\n'
                '  "permissions": { "file": { "read": [".agents/**"] } }\n'
                "}\n",
            )
            check = kilo_config_schema_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn("permissions", check["detail"])

    def test_missing_schema_declaration_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, '{ "permission": { "edit": "ask" } }\n')
            check = kilo_config_schema_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn("$schema", check["detail"])

    def test_unknown_permission_sub_key_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(
                root,
                '{ "$schema": "x", "permission": { "file": { "*": "allow" } } }\n',
            )
            check = kilo_config_schema_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn("file", check["detail"])

    def test_unknown_action_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, '{ "$schema": "x", "permission": { "edit": { "*": "block" } } }\n')
            check = kilo_config_schema_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn("block", check["detail"])

    def test_action_only_sub_key_rejects_a_pattern_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, '{ "$schema": "x", "permission": { "webfetch": { "*": "allow" } } }\n')
            check = kilo_config_schema_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn("bare action", check["detail"])

    def test_missing_or_unparseable_config_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(kilo_config_schema_check(root)["status"], "WARN")
            self._write(root, "{ not json")
            self.assertEqual(kilo_config_schema_check(root)["status"], "WARN")


class KiloDeniesGovernedArtifactEdits(unittest.TestCase):
    def test_repo_config_denies_every_governed_glob(self):
        check = kilo_governed_deny_check(REPO_ROOT)
        self.assertEqual(check["status"], "PASS", check["detail"])

    def test_dropping_a_governed_glob_warns(self):
        from sentinel.hooks_logic import GOVERNED_ARTIFACT_GLOBS

        kept = GOVERNED_ARTIFACT_GLOBS[1:]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rules = ", ".join(f'"{glob}": "deny"' for glob in kept)
            (root / "kilo.jsonc").write_text(
                '{ "$schema": "x", "permission": { "edit": { "*": "allow", ' + rules + " } } }\n",
                encoding="utf-8",
            )
            check = kilo_governed_deny_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn(GOVERNED_ARTIFACT_GLOBS[0], check["detail"])

    def test_an_allow_entry_does_not_count_as_a_deny(self):
        from sentinel.hooks_logic import GOVERNED_ARTIFACT_GLOBS

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rules = ", ".join(f'"{glob}": "allow"' for glob in GOVERNED_ARTIFACT_GLOBS)
            (root / "kilo.jsonc").write_text(
                '{ "$schema": "x", "permission": { "edit": { ' + rules + " } } }\n",
                encoding="utf-8",
            )
            self.assertEqual(kilo_governed_deny_check(root)["status"], "WARN")


class KiloPreAuthorizesTheSentinelCLI(unittest.TestCase):
    def test_repo_config_pre_authorizes_every_runtime_command(self):
        check = kilo_command_allowlist_check(REPO_ROOT)
        self.assertEqual(check["status"], "PASS", check["detail"])

    def test_a_narrow_pattern_leaves_commands_unauthorized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kilo.jsonc").write_text(
                '{ "$schema": "x", "permission": { "bash": { "python -m sentinel /doctor": "allow" } } }\n',
                encoding="utf-8",
            )
            check = kilo_command_allowlist_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn("/backlog", check["detail"])

    def test_an_ask_entry_does_not_count_as_pre_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kilo.jsonc").write_text(
                '{ "$schema": "x", "permission": { "bash": { "python -m sentinel *": "ask" } } }\n',
                encoding="utf-8",
            )
            self.assertEqual(kilo_command_allowlist_check(root)["status"], "WARN")


if __name__ == "__main__":
    unittest.main()
