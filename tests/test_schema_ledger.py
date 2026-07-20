"""IMP-177 (I1): schema ledger — every JSON schema is classified and well-formed.

11 of 19 schemas have no runtime consumer: they are documentary contracts for
agents, and nothing kept them following the runtime (`assumption.schema.json`
drifted three layers before IMP-164; `promotion_event` is one enum change from
the same bug). This ledger makes the debt visible and self-cleaning: each schema
is either runtime-enforced or listed in `SCHEMA_DOC_ONLY` with a reason, and the
doc-only set may only shrink. IMP-217 graduated the four agent-gap schemas
(annotation/challenge/scrutiny/implementability_probe) once a real field/enum
drift guard existed for them. IMP-221 (H11) graduated the three agent-facing
*parser* schemas (backlog_refinement/composition/implementation_feedback) the
same way: each carries an agent-authored payload through a runtime validator, and
test_agent_parser_schemas ties the schema enums/required fields to that validator.
The remaining doc-only schemas are documentary *output* contracts — the runtime
builds those artifacts in code and validates nothing against the file — so there
is no consumed payload to guard (IMP-221 seed: classify, don't inflate).
"""

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO / "sentinel" / "schemas"

# Schemas with a real content-drift guard: a test that fails if the schema drifts
# from the runtime/skill it describes. The runtime loads no schema file (validation
# is hand-rolled, stdlib-pure — IMP-103), so "enforced" here means "guarded":
# assumption.schema.json is checked field-for-field against its skill by
# AssumeContractGuardTests (IMP-164).
SCHEMA_RUNTIME_ENFORCED = {
    "assumption.schema.json",
    # IMP-217 (H10): the four agent-gap schemas are guarded field/enum-for-enum
    # against validate_agent_gaps by AgentGapSchemaDriftGuard (test_agent_gap_schemas.py).
    "annotation.schema.json",
    "challenge.schema.json",
    "scrutiny.schema.json",
    "implementability_probe.schema.json",
    # IMP-221 (H11): the three agent-facing parser schemas are guarded enum/required
    # -for-required against their runtime validators by test_agent_parser_schemas.py
    # (validate_proposal_shape / validate_block_shape / validate_finding_shape).
    "backlog_refinement.schema.json",
    "composition.schema.json",
    "implementation_feedback.schema.json",
}

# Documentary contracts with no drift guard yet, each one field/enum change from
# silent drift (assumption drifted three layers before IMP-164). The ledger only
# shrinks: when a schema gains a real guard, move it to SCHEMA_RUNTIME_ENFORCED
# and lower MAX_DOC_ONLY.
SCHEMA_DOC_ONLY = {
    "acceptance_criteria.schema.json": "documentary AC output contract; the runtime builds acceptance criteria in code",
    "change.schema.json": "documentary CHG output contract",
    "decision.schema.json": "documentary DEC output contract",
    "gap.schema.json": "documentary gap output contract; the runtime hand-rolls gap validation",
    "knowledge_unit.schema.json": "documentary knowledge-unit output contract",
    "promotion_event.schema.json": "documentary ledger-promotion output contract",
    "requirement.schema.json": "documentary requirement output contract",
    "requirement_unit.schema.json": "documentary RU output contract",
    "spec_unit.schema.json": "documentary SPEC-U output contract",
    "story.schema.json": "documentary US output contract",
    "traceability.schema.json": "documentary trace output contract",
}

MAX_DOC_ONLY = 11  # lower this whenever a schema graduates to a real drift guard


def _schema_files() -> set[str]:
    return {path.name for path in SCHEMA_DIR.glob("*.json")}


class SchemaStructuralValidity(unittest.TestCase):
    def test_every_schema_is_well_formed(self):
        for name in sorted(_schema_files()):
            data = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
            self.assertEqual(data.get("type"), "object", f"{name}: top-level type must be object")
            properties = data.get("properties")
            self.assertIsInstance(properties, dict, f"{name}: missing properties object")
            for field in data.get("required", []):
                self.assertIn(field, properties, f"{name}: required field '{field}' absent from properties")


class SchemaLedger(unittest.TestCase):
    def test_ledger_classifies_every_schema_exactly_once(self):
        files = _schema_files()
        enforced = set(SCHEMA_RUNTIME_ENFORCED)
        doc_only = set(SCHEMA_DOC_ONLY)
        self.assertEqual(enforced & doc_only, set(), "a schema is both enforced and doc-only")
        classified = enforced | doc_only
        self.assertEqual(
            classified,
            files,
            f"unclassified or stale schemas: {classified.symmetric_difference(files)}",
        )

    def test_doc_only_ledger_only_shrinks(self):
        self.assertLessEqual(
            len(SCHEMA_DOC_ONLY),
            MAX_DOC_ONLY,
            "doc-only ledger grew — validate the new schema against a real payload instead of parking it here",
        )

    def test_enforced_schemas_have_a_real_guard(self):
        # An "enforced" schema must be referenced by a guard test that is neither
        # the packaging existence test nor this ledger — i.e. something that
        # actually checks its content against the runtime/skill.
        excluded = {"test_package_resources.py", "test_schema_ledger.py"}
        guards = [path for path in (REPO / "tests").glob("test_*.py") if path.name not in excluded]
        for name in sorted(SCHEMA_RUNTIME_ENFORCED):
            referencing = [g.name for g in guards if name in g.read_text(encoding="utf-8", errors="ignore")]
            self.assertTrue(referencing, f"{name} is classified enforced but no guard test references it")


if __name__ == "__main__":
    unittest.main()
