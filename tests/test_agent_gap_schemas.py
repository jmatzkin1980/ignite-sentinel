"""IMP-217 (H10, F-SCHEMA-1/2): drift guard for the agent-gap schemas.

`/annotate`, `/challenge`, `/scrutinize` and the implementability probe all feed
their `gaps[]` array through the same code validator, `validate_agent_gaps`
(the runtime loads no schema file — validation is hand-rolled, stdlib-pure,
IMP-103). Their `.schema.json` files are documentary contracts for agents, and
nothing kept them following the validator (`assumption` drifted three layers
before IMP-164; the ledger flagged `scrutiny` as one enum change from the same
bug). This test IS that missing guard: it ties each schema's declared gap-item
contract to what `validate_agent_gaps` actually enforces, so a lens/severity/id
change on either side fails until both agree. That lets the four graduate to
SCHEMA_RUNTIME_ENFORCED in the ledger.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from sentinel.discovery import AnnotationError, GAP_ID_RE, known_lenses, validate_agent_gaps

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "sentinel" / "schemas"

# The four schemas whose gaps[] items are validated by validate_agent_gaps.
AGENT_GAP_SCHEMAS = (
    "annotation.schema.json",
    "challenge.schema.json",
    "scrutiny.schema.json",
    "implementability_probe.schema.json",
)

# The contract validate_agent_gaps enforces field-for-field (workflow.py).
CORE_REQUIRED = {"id", "lens", "severity", "question", "evidence"}
RUNTIME_SEVERITIES = {"critical", "high", "medium", "low"}

RAW = "# Raw\n\nThe support dashboard must show ticket volume for the current quarter.\n"
EVIDENCE = "ticket volume for the current quarter"


def _gap_items(name: str) -> dict:
    data = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    return data["properties"]["gaps"]["items"]


class AgentGapSchemaDriftGuard(unittest.TestCase):
    def test_schema_gap_contract_matches_runtime_validator(self) -> None:
        runtime_lenses = set(known_lenses())
        for name in AGENT_GAP_SCHEMAS:
            items = _gap_items(name)
            required = set(items["required"])
            props = items["properties"]
            self.assertLessEqual(
                CORE_REQUIRED, required, f"{name}: gap items must require the core fields the validator enforces"
            )
            self.assertEqual(
                set(props["lens"]["enum"]), runtime_lenses, f"{name}: lens enum drifted from known_lenses()"
            )
            self.assertEqual(
                set(props["severity"]["enum"]), RUNTIME_SEVERITIES, f"{name}: severity enum drifted from the validator"
            )
            self.assertEqual(
                props["id"]["pattern"], GAP_ID_RE.pattern, f"{name}: id pattern drifted from GAP_ID_RE"
            )

    def test_runtime_validator_accepts_schema_shaped_gap_and_rejects_violations(self) -> None:
        # Anchor the structural checks to real behavior: a gap built to the shared
        # contract is accepted, and violating the declared enums is rejected.
        valid = {"id": "GAP-ONE", "lens": "product", "severity": "high", "question": "Q?", "evidence": EVIDENCE}
        self.assertEqual(validate_agent_gaps({"gaps": [valid]}, RAW)[0]["origin"], "agent")
        for bad in ({**valid, "lens": "not-a-lens"}, {**valid, "severity": "urgent"}, {**valid, "id": "BAD-1"}):
            with self.assertRaises(AnnotationError):
                validate_agent_gaps({"gaps": [bad]}, RAW)


if __name__ == "__main__":
    unittest.main()
