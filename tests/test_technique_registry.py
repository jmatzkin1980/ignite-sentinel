"""Tests for the declarative /challenge technique registry (IMP-112)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel import technique_registry
from sentinel.discovery.workflow import CHALLENGE_TECHNIQUES, render_challenge_report

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_TECHNIQUES = REPO_ROOT / "sentinel" / "techniques"


class TechniqueRegistryShapeTests(unittest.TestCase):
    def tearDown(self) -> None:
        technique_registry.clear_cache()

    def test_registry_loads_and_default_matches_challenge_behavior(self):
        techniques = technique_registry.load_techniques()
        ids = [item["id"] for item in techniques]
        self.assertGreaterEqual(len(ids), 6)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(("pre-mortem", "role-play", "assumption-inversion", "jtbd-forces"), CHALLENGE_TECHNIQUES)
        self.assertEqual(CHALLENGE_TECHNIQUES, technique_registry.default_challenge_technique_ids())
        self.assertIn("jtbd-forces", ids)
        self.assertIn("red-blue-team", ids)
        self.assertIn("first-principles", ids)
        self.assertIn("stakeholder-round-robin", ids)
        for technique in techniques:
            self.assertIn(technique["category"], technique_registry.VALID_CATEGORIES)
            self.assertTrue(technique["name"])
            self.assertTrue(technique["prompt"])
            self.assertIn("business", technique["calibration"])
            self.assertIn("technical", technique["calibration"])
            self.assertTrue(technique["evidence_contract"])

    def test_technique_prompt_preserves_default_without_declared_profile(self):
        technique = technique_registry.technique_by_id("pre-mortem")

        self.assertEqual(technique["prompt"], technique_registry.technique_prompt("pre-mortem"))
        self.assertEqual(
            technique["prompt"],
            technique_registry.technique_prompt("pre-mortem", respondent_profile="architect"),
        )

    def test_technique_prompt_uses_declared_profile_calibration(self):
        technique = technique_registry.technique_by_id("pre-mortem")

        technical = technique_registry.technique_prompt("pre-mortem", respondent_profile="technical")
        business = technique_registry.technique_prompt("pre-mortem", respondent_profile="negocio")

        self.assertIn(technique["prompt"], technical)
        self.assertIn(technique["calibration"]["technical"], technical)
        self.assertIn(technique["calibration"]["business"], business)

    def test_report_uses_registry_labels_without_changing_merge_contract(self):
        report = render_challenge_report(
            "CHL",
            "source",
            [
                {
                    "id": "GAP-TEST",
                    "lens": "product",
                    "severity": "medium",
                    "question": "What decision is missing?",
                    "evidence_mention": "must decide",
                }
            ],
            [],
            {"gaps": [{"id": "GAP-TEST", "technique": "role-play"}]},
        )
        self.assertIn("Technique catalog: `sentinel/techniques/*.json`", report)
        self.assertIn("per-lens role-play", report)

    def test_report_materializes_calibrated_prompts_for_declared_profile(self):
        report = render_challenge_report("CHL", "source", [], [], {}, respondent_profile="technical")

        self.assertIn("Declared respondent profile: `technical`", report)
        self.assertIn("Calibrated technique prompts:", report)
        self.assertIn("implementation surfaces", report)


class PreMortemRiskTaxonomyTests(unittest.TestCase):
    """IMP-195: Tigers / Paper Tigers / Elephants taxonomy on the pre-mortem technique."""

    def tearDown(self) -> None:
        technique_registry.clear_cache()

    def test_pre_mortem_declares_the_closed_taxonomy(self):
        taxonomy = technique_registry.technique_risk_taxonomy("pre-mortem")
        labels = [row["label"] for row in taxonomy]
        self.assertEqual(labels, list(technique_registry.RISK_TAXONOMY_LABELS))
        for row in taxonomy:
            self.assertTrue(row["definition"])
            self.assertTrue(row["response"])

    def test_other_techniques_have_empty_taxonomy(self):
        self.assertEqual(technique_registry.technique_risk_taxonomy("role-play"), [])

    def test_unknown_label_is_rejected(self):
        with self.assertRaises(ValueError):
            technique_registry.normalize_risk_taxonomy(
                [{"label": "Dragon", "definition": "x", "response": "y"}], "pre-mortem"
            )

    def test_duplicate_label_is_rejected(self):
        with self.assertRaises(ValueError):
            technique_registry.normalize_risk_taxonomy(
                [
                    {"label": "Tiger", "definition": "a", "response": "b"},
                    {"label": "Tiger", "definition": "c", "response": "d"},
                ],
                "pre-mortem",
            )

    def test_missing_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            technique_registry.normalize_risk_taxonomy(
                [{"label": "Elephant", "definition": "", "response": "act"}], "pre-mortem"
            )

    def test_absent_taxonomy_is_empty(self):
        self.assertEqual(technique_registry.normalize_risk_taxonomy(None), [])
        self.assertEqual(technique_registry.normalize_risk_taxonomy([]), [])

    def test_challenge_report_surfaces_taxonomy(self):
        report = render_challenge_report("CHL", "source", [], [], {})
        for label in technique_registry.RISK_TAXONOMY_LABELS:
            self.assertIn(label, report)
        self.assertIn("How to respond", report)


class AddTechniqueWithoutPythonTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="technique_test_")
        self.tmp = Path(self.tmpdir)
        shutil.copytree(REAL_TECHNIQUES, self.tmp / "techniques")
        extra = {
            "id": "decision-forcing",
            "name": "decision forcing",
            "category": "decomposition",
            "default": False,
            "prompt": "Force every implied decision into an explicit evidence-backed question.",
            "evidence_contract": "No decision can become a gap without a verbatim local quote.",
            "output_focus": ["decision", "evidence", "question"],
        }
        (self.tmp / "techniques" / "decision-forcing.json").write_text(
            json.dumps(extra, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        technique_registry.clear_cache()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        technique_registry.clear_cache()

    def test_new_technique_loads_from_json_only(self):
        ids = technique_registry.known_technique_ids(self.tmp / "techniques")
        self.assertIn("decision-forcing", ids)
        loaded = technique_registry.technique_by_id("decision-forcing", self.tmp / "techniques")
        self.assertEqual("decision forcing", loaded["name"])
        self.assertNotIn("decision-forcing", technique_registry.default_challenge_technique_ids(self.tmp / "techniques"))


if __name__ == "__main__":
    unittest.main()
