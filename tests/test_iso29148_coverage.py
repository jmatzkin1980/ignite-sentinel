"""IMP-189: ISO/IEC/IEEE 29148 requirement-quality rubric mapped to checks.

The nine individual-requirement characteristics are declared once; each existing
deterministic check declares which of them it covers (`covers_29148`). The
coverage report joins the two and is honest about the gap: a characteristic is
covered, an open heuristic gap, or declared out of scope with a reason — it
never simulates coverage for something a local heuristic cannot decide
(adversarial seed doc 39 §4.6, e.g. "Complete"). The one live rule this feature
adds, verifiability of a requirement statement, catches statements that every
existing check leaves unscrutinized.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.ears import score_requirement_quality
from sentinel.iso29148 import (
    CHARACTERISTIC_ORDER,
    coverage_by_characteristic,
    coverage_report,
    load_characteristics,
    load_check_catalog,
    verifiability_findings,
)
from sentinel.validation import validate_project

ROOT = Path(__file__).parent


class CharacteristicRegistryTests(unittest.TestCase):
    def test_exactly_the_nine_iso_characteristics_in_canonical_order(self):
        ids = [char["id"] for char in load_characteristics()]
        self.assertEqual(ids, list(CHARACTERISTIC_ORDER))
        self.assertEqual(len(ids), 9)

    def test_every_characteristic_has_label_and_description(self):
        for char in load_characteristics():
            self.assertTrue(char["label"], char["id"])
            self.assertTrue(char["description"], char["id"])
            self.assertIn(char["when_uncovered"], {"heuristic_gap", "out_of_scope"})


class CheckCatalogTests(unittest.TestCase):
    def test_catalog_only_references_declared_characteristics(self):
        known = {char["id"] for char in load_characteristics()}
        for check in load_check_catalog():
            for char_id in check["covers_29148"]:
                self.assertIn(char_id, known, f"{check['id']} maps to unknown characteristic {char_id}")

    def test_new_verifiability_rule_is_catalogued(self):
        catalog = {check["id"]: check for check in load_check_catalog()}
        self.assertIn("iso29148.verifiability_anchor", catalog)
        self.assertEqual(catalog["iso29148.verifiability_anchor"]["covers_29148"], ["verifiable"])
        self.assertEqual(catalog["iso29148.verifiability_anchor"]["imp"], "IMP-189")

    def test_momtest_declares_no_forced_mapping(self):
        catalog = {check["id"]: check for check in load_check_catalog()}
        self.assertEqual(catalog["momtest.hypothetical"]["covers_29148"], [])


class CoverageReportTests(unittest.TestCase):
    def setUp(self):
        self.report = coverage_report()
        self.rows = {row["id"]: row for row in self.report["characteristics"]}

    def test_report_shape_and_serializable(self):
        json.dumps(self.report)  # must survive /validate's print_json
        self.assertEqual(self.report["standard"], "ISO/IEC/IEEE 29148:2018")
        self.assertEqual(len(self.report["characteristics"]), 9)

    def test_covered_characteristics_have_at_least_one_check(self):
        for char_id in ("unambiguous", "singular", "conforming", "verifiable"):
            self.assertEqual(self.rows[char_id]["status"], "covered", char_id)
            self.assertTrue(self.rows[char_id]["covered_by"], char_id)

    def test_out_of_scope_characteristics_are_declared_with_a_reason(self):
        for char_id in ("necessary", "complete", "feasible", "correct"):
            row = self.rows[char_id]
            self.assertEqual(row["status"], "out_of_scope", char_id)
            self.assertFalse(row["covered_by"], char_id)
            self.assertTrue(row["reason"], char_id)

    def test_complete_is_not_simulated(self):
        # Adversarial seed §4.6: "Complete" must be out of scope, never faked.
        self.assertEqual(self.rows["complete"]["status"], "out_of_scope")
        self.assertIn("domain", self.rows["complete"]["reason"].lower())

    def test_appropriate_is_an_honest_heuristic_gap(self):
        row = self.rows["appropriate"]
        self.assertEqual(row["status"], "heuristic_gap")
        self.assertFalse(row["covered_by"])
        self.assertTrue(row["reason"])

    def test_every_uncovered_characteristic_carries_a_reason(self):
        for row in self.report["characteristics"]:
            if row["status"] != "covered":
                self.assertTrue(row["reason"], row["id"])

    def test_summary_counts_match_rows(self):
        summary = self.report["summary"]
        self.assertEqual(summary["total"], 9)
        self.assertEqual(summary["covered"], 4)
        self.assertEqual(summary["heuristic_gap"], 1)
        self.assertEqual(summary["out_of_scope"], 4)

    def test_coverage_map_wires_verifiable_to_the_new_rule(self):
        self.assertIn("iso29148.verifiability_anchor", coverage_by_characteristic()["verifiable"])


class VerifiabilityRuleTests(unittest.TestCase):
    PRIMARY = (
        "# Requirement Register - DEMO\n\n"
        "## REQ-001 Primary Requirement\n\n"
        "- Source: `RAW-001`\n\n"
        "{primary}\n\n"
        "## Normalized Requirements (EARS)\n\n"
        "| ID | Pattern | Statement | Source |\n"
        "| --- | --- | --- | --- |\n"
        "| REQ-EARS-001 | ubiquitous | {ears} | `GAP-001` |\n"
    )

    def _findings(self, primary: str, ears: str) -> dict[str, dict]:
        markdown = self.PRIMARY.format(primary=primary, ears=ears)
        return {f["statement_id"]: f for f in verifiability_findings(markdown)}

    def test_well_formed_ears_without_anchor_is_flagged_where_existing_checks_are_silent(self):
        statement = "The system shall display the queue."
        # Every existing requirement-quality signal passes this statement.
        self.assertEqual(score_requirement_quality(statement)["signals"], [])
        findings = self._findings("The team needs visibility.", statement)
        self.assertIn("REQ-EARS-001", findings)
        self.assertEqual(findings["REQ-EARS-001"]["characteristic"], "verifiable")
        self.assertEqual(findings["REQ-EARS-001"]["statement"], statement)

    def test_statement_with_measurable_anchor_is_silent(self):
        findings = self._findings(
            "The dashboard shall load within 5 seconds.",
            "When a case breaches SLA, the system shall flag the queue within 5 minutes.",
        )
        self.assertEqual(findings, {})

    def test_statement_with_acceptance_word_is_silent(self):
        findings = self._findings(
            "Each report must pass the acceptance test before release.",
            "The system shall verify the invoice total.",
        )
        self.assertEqual(findings, {})

    def test_no_requirements_text_yields_no_findings(self):
        self.assertEqual(verifiability_findings(""), [])


class ValidateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "ISO"]), 0)
        self.assertEqual(main(["ingest", "ISO", "--source", str(fixture)]), 0)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_validate_includes_iso29148_coverage(self):
        result = validate_project("ISO")
        self.assertIn("iso29148_coverage", result)
        coverage = result["iso29148_coverage"]
        self.assertEqual(coverage["summary"]["total"], 9)
        self.assertEqual(coverage["standard"], "ISO/IEC/IEEE 29148:2018")
        # The whole validate result is printed as JSON by the CLI.
        json.dumps(result)


if __name__ == "__main__":
    unittest.main()
