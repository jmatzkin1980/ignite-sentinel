"""IMP-221 (H11, F-SCHEMA-1 rest): drift guard for the three agent-facing
*parser* schemas, graduating them from doc-only to runtime-enforced.

`/refine-backlog`, `/compose` and `/implementation-feedback` each take an
agent-authored JSON payload and feed it through a hand-rolled runtime validator
(the runtime loads no schema file — validation is stdlib-pure, IMP-103). Their
`.schema.json` files are the documented contract the agent writes against, but
nothing kept them following the validator (`assumption` drifted three layers
before IMP-164; the same latent bug is one enum change away here). This test IS
that missing guard: for each schema it ties the declared enums / required fields
to what the validator actually enforces, and anchors that to real behaviour (a
schema-shaped payload is accepted; violating a declared enum/required field is
rejected). A change on either side fails until both agree, which is what lets the
three graduate to SCHEMA_RUNTIME_ENFORCED in the ledger (mirrors IMP-217's
graduation of the four agent-gap schemas).

Only the fields the validator genuinely enforces are asserted; purely optional,
non-consumed fields are left alone (IMP-221 seed: classify, don't inflate).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from sentinel.backlog.refinement import VALID_KINDS, validate_proposal_shape
from sentinel.implementation_feedback import (
    VALID_FINDING_TYPES,
    VALID_STATUSES,
    validate_finding_shape,
)
from sentinel.prd import validate_block_shape

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "sentinel" / "schemas"

# Schema file names, referenced verbatim so the ledger's "enforced schemas have a
# real guard" test can find this guard by name.
REFINEMENT_SCHEMA = "backlog_refinement.schema.json"
COMPOSITION_SCHEMA = "composition.schema.json"
FEEDBACK_SCHEMA = "implementation_feedback.schema.json"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _items(name: str) -> dict:
    """The item schema of the single top-level array each contract carries."""
    props = _schema(name)["properties"]
    (array_field,) = props.keys()
    return props[array_field]["items"]


class BacklogRefinementSchemaDriftGuard(unittest.TestCase):
    # The verbatim source-of-truth the citation must quote, plus a two-story
    # backlog the validator resolves target_stories against.
    EVIDENCE = "the support dashboard must show ticket volume for the current quarter"
    STORY_INDEX = {"US-001": {"pending": False}, "US-002": {"pending": False}}
    SPEC_UNITS = {"SPEC-U-001": "the dashboard renders ticket volume"}

    def test_schema_contract_matches_validator(self) -> None:
        items = _items(REFINEMENT_SCHEMA)
        self.assertEqual(
            set(items["properties"]["kind"]["enum"]),
            VALID_KINDS,
            "backlog_refinement kind enum drifted from VALID_KINDS",
        )
        # Fields the validator hard-requires on every proposal.
        self.assertEqual(
            set(items["required"]),
            {"kind", "recommendation", "rationale", "citations"},
            "backlog_refinement required set drifted from validate_proposal_shape",
        )
        # The enabler-candidate branch requires the concrete-enabler fields the
        # validator enforces in validate_enabler_candidate.
        enabler_then = items["allOf"][0]["then"]["required"]
        self.assertEqual(
            set(enabler_then),
            {
                "enables_stories",
                "supports_boundary",
                "enabled_capability",
                "verification_method",
                "risk_reduced",
                "objective_evidence",
            },
            "backlog_refinement enabler-candidate required set drifted from validate_enabler_candidate",
        )

    def test_validator_accepts_schema_shaped_proposal_and_rejects_violations(self) -> None:
        valid = {
            "kind": "merge-stories",
            "target_stories": ["US-001", "US-002"],
            "recommendation": "Merge the duplicated stories.",
            "rationale": "Both cover the same dashboard view.",
            "citations": ["ticket volume for the current quarter"],
        }
        self.assertEqual(
            validate_proposal_shape(valid, self.EVIDENCE, self.STORY_INDEX, self.SPEC_UNITS),
            "",
        )
        for bad in (
            {**valid, "kind": "not-a-kind"},
            {**valid, "citations": []},
            {**valid, "recommendation": ""},
        ):
            self.assertNotEqual(
                validate_proposal_shape(bad, self.EVIDENCE, self.STORY_INDEX, self.SPEC_UNITS),
                "",
                f"validator accepted a violating proposal: {bad}",
            )


class CompositionSchemaDriftGuard(unittest.TestCase):
    EVIDENCE = "reduce manual preparation by 30 percent in the first release month"
    SECTIONS = {"2": "Scope: the read-only risk dashboard."}

    def test_schema_contract_matches_validator(self) -> None:
        block = _items(COMPOSITION_SCHEMA)
        self.assertEqual(
            set(block["required"]),
            {"section", "paragraphs"},
            "composition block required set drifted from validate_block_shape",
        )
        paragraph = block["properties"]["paragraphs"]["items"]
        self.assertEqual(
            set(paragraph["required"]),
            {"text", "citations"},
            "composition paragraph required set drifted from validate_block_shape",
        )

    def test_validator_accepts_schema_shaped_block_and_rejects_violations(self) -> None:
        valid = {
            "section": "2",
            "paragraphs": [
                {
                    "text": "The dashboard is read-only.",
                    "citations": ["reduce manual preparation by 30 percent"],
                }
            ],
        }
        self.assertEqual(validate_block_shape(valid, "2", self.SECTIONS, self.EVIDENCE), "")
        # section absent from the PRD, empty citations, empty text: each rejected.
        self.assertNotEqual(validate_block_shape(valid, "9", self.SECTIONS, self.EVIDENCE), "")
        no_citations = {"section": "2", "paragraphs": [{"text": "X.", "citations": []}]}
        self.assertNotEqual(validate_block_shape(no_citations, "2", self.SECTIONS, self.EVIDENCE), "")
        empty_text = {
            "section": "2",
            "paragraphs": [{"text": "", "citations": ["reduce manual preparation by 30 percent"]}],
        }
        self.assertNotEqual(validate_block_shape(empty_text, "2", self.SECTIONS, self.EVIDENCE), "")


class ImplementationFeedbackSchemaDriftGuard(unittest.TestCase):
    STORY_INDEX = {"US-001": {"acceptance_criteria": {"AC-001-01"}}}

    def test_schema_contract_matches_validator(self) -> None:
        finding = _items(FEEDBACK_SCHEMA)["properties"]
        self.assertEqual(
            set(finding["type"]["enum"]),
            VALID_FINDING_TYPES,
            "implementation_feedback type enum drifted from VALID_FINDING_TYPES",
        )
        self.assertEqual(
            set(finding["status"]["enum"]),
            VALID_STATUSES,
            "implementation_feedback status enum drifted from VALID_STATUSES",
        )
        # The validator requires type + summary + evidence + a story reference.
        item_required = set(_items(FEEDBACK_SCHEMA)["required"])
        self.assertEqual(
            item_required,
            {"type", "summary", "evidence"},
            "implementation_feedback required set drifted from validate_finding_shape",
        )

    def test_validator_accepts_schema_shaped_finding_and_rejects_violations(self) -> None:
        valid = {"type": "gap", "story": "US-001", "summary": "Missing rule.", "evidence": "seen in code"}
        self.assertEqual(validate_finding_shape(valid, self.STORY_INDEX), "")
        for bad in (
            {**valid, "type": "not-a-type"},
            {**valid, "status": "urgent"},
            {**valid, "story": "US-999"},
            {**valid, "evidence": ""},
        ):
            self.assertNotEqual(
                validate_finding_shape(bad, self.STORY_INDEX),
                "",
                f"validator accepted a violating finding: {bad}",
            )


if __name__ == "__main__":
    unittest.main()
