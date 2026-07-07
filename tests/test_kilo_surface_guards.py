"""Anti-drift guards for the handcrafted Kilo agents (IMP-173).

Kilo has no skills — the 7 agents in ``.kilo/agents/`` are its model-facing depth
and are maintained by hand (no generator). Before IMP-173 they were frozen at
~IMP-058: they invited hand-editing/patching of governed artifacts and knew none
of the H1-H5 runtime. These guards (mirroring the skill mention-checks of
IMP-163) fail if a forbidden invitation returns or a required capability mention
is lost, and lean on the new ``/doctor`` frontmatter check.
"""

import re
import tempfile
import unittest
from pathlib import Path

from sentinel.doctor import REQUIRED_KILO_AGENTS, kilo_agent_metadata_checks

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


if __name__ == "__main__":
    unittest.main()
