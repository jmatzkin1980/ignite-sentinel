"""Tests for the declarative Cagan risk-category registry (IMP-181)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel import risk_category_registry

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_RISK_CATEGORIES = REPO_ROOT / "sentinel" / "risk_categories"


class RiskCategoryRegistryShapeTests(unittest.TestCase):
    def tearDown(self) -> None:
        risk_category_registry.clear_cache()

    def test_default_registry_has_the_four_cagan_categories(self):
        categories = risk_category_registry.load_risk_categories()
        ids = [category["id"] for category in categories]
        self.assertEqual(ids, ["value", "usability", "viability", "feasibility"])
        self.assertEqual(
            risk_category_registry.known_risk_categories(),
            {"value", "usability", "viability", "feasibility"},
        )
        for category in categories:
            self.assertTrue(category["label"])
            self.assertTrue(category["description"])

    def test_risk_category_label_returns_declared_label(self):
        self.assertEqual(risk_category_registry.risk_category_label("viability"), "Business viability")
        self.assertEqual(risk_category_registry.risk_category_label("unknown"), "Unknown")


class ExtendRiskCategoriesWithoutPythonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="risk_category_test_")
        self.tmp = Path(self.tmpdir)
        shutil.copytree(REAL_RISK_CATEGORIES, self.tmp / "risk_categories")
        extra = {
            "id": "go-to-market",
            "label": "Go-to-market",
            "description": "Extended category added via directory override, not the default Cagan four.",
        }
        (self.tmp / "risk_categories" / "go-to-market.json").write_text(
            json.dumps(extra, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        risk_category_registry.clear_cache()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        risk_category_registry.clear_cache()

    def test_extended_category_loads_from_json_only(self):
        directory = self.tmp / "risk_categories"
        ids = risk_category_registry.known_risk_categories(directory)
        self.assertIn("go-to-market", ids)
        self.assertIn("value", ids)
        label = risk_category_registry.risk_category_label("go-to-market", directory)
        self.assertEqual(label, "Go-to-market")


if __name__ == "__main__":
    unittest.main()
