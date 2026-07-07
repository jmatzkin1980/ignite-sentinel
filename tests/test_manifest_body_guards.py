"""IMP-174: anti-drift guards between the command manifest bodies and the runtime.

The manifest bodies are the source of `.claude/commands/` and `.kilo/commands/`.
`test_command_adapters_in_sync_with_manifest` already guards byte-sync and name
parity, but nothing guarded the body *content* against the runtime — so several
bodies drifted behind H1-H5 (challenge missing extended techniques/respondent
profile, resolve-gaps missing the closure matrix, health blind to staleness/
artifact hashes, sync missing ASM invalidation and still inviting patching).
These guards, in the mold of the router/technique guards (IMP-163), anchor the
bodies to runtime vocabulary so that class of drift fails the suite.
"""

import re
import unittest

from sentinel.adapters import load_manifest
from sentinel.technique_registry import TECHNIQUE_ORDER

# Matches the verb "patch"/"patching" in prose, not identifiers like `apply_patch`.
FORBIDDEN_INVITATIONS = re.compile(r"manual artifact edits|(?<!\w)patch", re.IGNORECASE)

# Runtime vocabulary each body must carry so it cannot silently fall behind the
# semantics/options that affect invocation.
REQUIRED_BODY_MENTIONS = {
    "resolve-gaps": ["CLOSED", "ANSWERED", "PARTIALLY_CLOSED", "OPEN", "EARS"],
    "health": ["staleness", "artifact_hashes", "needs_context"],
    "sync": ["ASM-", "origin: sync", "superseded", "associative"],
}


def _bodies():
    return {entry["name"]: entry["body"] for entry in load_manifest()["commands"]}


class ChallengeBodyGuard(unittest.TestCase):
    def test_body_lists_every_registry_technique_and_respondent_profile(self):
        body = _bodies()["challenge"]
        for technique in TECHNIQUE_ORDER:
            self.assertIn(technique, body, f"challenge body omits registry technique {technique}")
        self.assertIn("respondent_profile", body)


class BodyMentionGuards(unittest.TestCase):
    def test_required_runtime_mentions_present(self):
        bodies = _bodies()
        for name, tokens in REQUIRED_BODY_MENTIONS.items():
            body = bodies[name]
            for token in tokens:
                self.assertIn(token, body, f"{name} body lost required runtime mention: {token!r}")


class BodiesFreeOfHandEditInvitations(unittest.TestCase):
    def test_no_body_invites_hand_editing_or_patching(self):
        for name, body in _bodies().items():
            self.assertIsNone(
                FORBIDDEN_INVITATIONS.search(body),
                f"manifest body '{name}' invites hand-editing/patching of governed artifacts",
            )


if __name__ == "__main__":
    unittest.main()
