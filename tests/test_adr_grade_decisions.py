"""IMP-188: ADR-grade decisions — cited trade-offs, cited options, immutable supersession.

A hard-to-reverse decision earns ADR discipline: it may declare the trade-offs it
accepts (`consequences`), the alternatives that were on the table (`considered_options`,
each cited verbatim so the choice cannot be relitigated later), and an immutable
`supersedes` back-reference (a decision is never edited in place — a new one replaces
it, molde invalidar-no-borrar IMP-153). Every new field is optional and additive:
an older payload that only carried `consequence` still validates unchanged.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.decisions import validate_cited_decisions
from sentinel.discovery import AnnotationError


GROUNDING = (
    "The CRM emits invoice updates nightly. "
    "Users submit invoices for billing. "
    "Real-time sync was raised as an option."
)


def _decision(**overrides) -> dict:
    base = {
        "id": "DEC-SCOPE-LOCK",
        "title": "Nightly batch is authoritative",
        "lens": "technical",
        "risk": "high",
        "reversibility": "hard-to-reverse",
        "decision": "Specs assume the nightly batch contract.",
        "evidence": "The CRM emits invoice updates nightly",
    }
    base.update(overrides)
    return base


class BackwardsCompatibilityTests(unittest.TestCase):
    def test_legacy_payload_without_new_fields_still_validates(self):
        data = {"decisions": [_decision(consequence="Real-time expectations must be renegotiated.")]}
        decisions = validate_cited_decisions(data, GROUNDING, label="test")
        self.assertEqual(decisions[0]["consequence"], "Real-time expectations must be renegotiated.")
        # New fields default to empty — no migration required.
        self.assertEqual(decisions[0]["consequences"], [])
        self.assertEqual(decisions[0]["considered_options"], [])
        self.assertEqual(decisions[0]["supersedes"], "")


class ConsequencesTests(unittest.TestCase):
    def test_consequences_list_is_parsed_and_trimmed(self):
        data = {"decisions": [_decision(consequences=["Trade-off A", "  Trade-off B  ", ""])]}
        decisions = validate_cited_decisions(data, GROUNDING, label="test")
        self.assertEqual(decisions[0]["consequences"], ["Trade-off A", "Trade-off B"])

    def test_consequences_must_be_a_list(self):
        data = {"decisions": [_decision(consequences="not a list")]}
        with self.assertRaises(AnnotationError):
            validate_cited_decisions(data, GROUNDING, label="test")


class ConsideredOptionsTests(unittest.TestCase):
    def test_cited_option_is_accepted(self):
        data = {"decisions": [_decision(considered_options=[
            {"option": "Real-time sync", "evidence": "Real-time sync was raised as an option"},
        ])]}
        decisions = validate_cited_decisions(data, GROUNDING, label="test")
        self.assertEqual(decisions[0]["considered_options"][0]["option"], "Real-time sync")

    def test_uncited_option_is_rejected(self):
        data = {"decisions": [_decision(considered_options=[{"option": "Real-time sync"}])]}
        with self.assertRaises(AnnotationError):
            validate_cited_decisions(data, GROUNDING, label="test")

    def test_option_with_non_verbatim_evidence_is_rejected(self):
        data = {"decisions": [_decision(considered_options=[
            {"option": "Real-time sync", "evidence": "realtime streaming was proposed"},
        ])]}
        with self.assertRaises(AnnotationError):
            validate_cited_decisions(data, GROUNDING, label="test")


class SupersedesTests(unittest.TestCase):
    def test_valid_reference_is_normalized(self):
        data = {"decisions": [_decision(id="DEC-B", supersedes="dec-a")]}
        decisions = validate_cited_decisions(data, GROUNDING, label="test")
        self.assertEqual(decisions[0]["supersedes"], "DEC-A")

    def test_malformed_reference_is_rejected(self):
        data = {"decisions": [_decision(supersedes="A-123")]}
        with self.assertRaises(AnnotationError):
            validate_cited_decisions(data, GROUNDING, label="test")

    def test_self_supersession_is_rejected(self):
        data = {"decisions": [_decision(id="DEC-B", supersedes="DEC-B")]}
        with self.assertRaises(AnnotationError):
            validate_cited_decisions(data, GROUNDING, label="test")


ROOT = Path(__file__).parent


class SupersessionLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "ADR"]), 0)
        self.assertEqual(main(["ingest", "ADR", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "ADR"]), 0)
        self.assertEqual(main(["specs", "ADR"]), 0)
        self.base = self.temp / "workspaces" / "ADR"
        prd = self.base / "03_specs" / "prd.md"
        self.quote = next(
            line.strip() for line in prd.read_text(encoding="utf-8").splitlines() if "billing" in line.lower()
        )

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _gap(self) -> dict:
        return {
            "id": "GAP-ADR-ROLLBACK",
            "lens": "product",
            "severity": "medium",
            "question": "What rollback impact follows from the excluded scope decision?",
            "evidence": self.quote,
        }

    def _write_source(self, name: str, decision: dict) -> Path:
        source = self.temp / name
        source.write_text(json.dumps({"gaps": [self._gap()], "decisions": [decision]}), encoding="utf-8")
        return source

    def test_register_renders_adr_grade_fields_and_supersession(self):
        source = self.temp / "batch.json"
        source.write_text(
            json.dumps({"gaps": [self._gap()], "decisions": [
                {
                    "id": "DEC-SCOPE-DRAFT",
                    "title": "Draft scope lock",
                    "lens": "product",
                    "risk": "med",
                    "reversibility": "moderate",
                    "decision": "Draft: billing is committed.",
                    "evidence": self.quote,
                },
                {
                    "id": "DEC-SCOPE-FINAL",
                    "title": "Final scope lock",
                    "lens": "product",
                    "risk": "high",
                    "reversibility": "hard-to-reverse",
                    "decision": "Final: billing is committed with acceptance criteria.",
                    "evidence": self.quote,
                    "consequences": ["Changing this later invalidates backlog slicing."],
                    "considered_options": [{"option": "Defer billing", "evidence": self.quote}],
                    "supersedes": "DEC-SCOPE-DRAFT",
                },
            ]}),
            encoding="utf-8",
        )
        self.assertEqual(main(["self-review", "ADR", "--source", str(source)]), 0)

        # The register renders every decision, its ADR-grade fields, and the supersession.
        register = (self.base / "03_specs" / "self_review" / "decision_register.md").read_text(encoding="utf-8")
        self.assertIn("DEC-SCOPE-DRAFT", register)
        self.assertIn("DEC-SCOPE-FINAL", register)
        self.assertIn("Supersedes: `DEC-SCOPE-DRAFT`", register)
        self.assertIn("Consequences (trade-offs):", register)
        self.assertIn("Considered options:", register)
        self.assertIn("**Defer billing**", register)

        report = (self.base / "03_specs" / "self_review" / "self_review_report.md").read_text(encoding="utf-8")
        self.assertIn("`DEC-SCOPE-FINAL` supersedes `DEC-SCOPE-DRAFT`", report)

    def test_supersession_keeps_original_archived_source_intact(self):
        first = self._write_source("sr1.json", {
            "id": "DEC-SYNC-V1",
            "title": "Nightly batch is authoritative",
            "lens": "technical",
            "risk": "high",
            "reversibility": "hard-to-reverse",
            "decision": "Specs assume the nightly batch contract.",
            "evidence": self.quote,
        })
        self.assertEqual(main(["self-review", "ADR", "--source", str(first)]), 0)
        archive = self.base / "03_specs" / "self_review" / "sr1.json"
        archived_before = archive.read_text(encoding="utf-8")

        second = self._write_source("sr2.json", {
            "id": "DEC-SYNC-V2",
            "title": "Real-time sync becomes authoritative",
            "lens": "technical",
            "risk": "high",
            "reversibility": "hard-to-reverse",
            "decision": "Specs now assume a real-time sync contract.",
            "evidence": self.quote,
            "supersedes": "DEC-SYNC-V1",
        })
        self.assertEqual(main(["self-review", "ADR", "--source", str(second)]), 0)

        # Immutability: the prior decision is never edited — its archived source
        # stays byte-identical; the new decision only records the supersession.
        self.assertEqual(archive.read_text(encoding="utf-8"), archived_before)
        self.assertIn("DEC-SYNC-V1", archived_before)
        register = (self.base / "03_specs" / "self_review" / "decision_register.md").read_text(encoding="utf-8")
        self.assertIn("Supersedes: `DEC-SYNC-V1`", register)


if __name__ == "__main__":
    unittest.main()
