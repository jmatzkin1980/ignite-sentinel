"""Tests for the declarative lens knowledge base (IMP-033).

Proves the acceptance criterion: a check added by editing only a lens JSON file
(no Python change) shows up both in discovery gap detection and in the domain
context-request. Also guards that the registry stays well-formed.
"""
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from sentinel import lens_registry
from sentinel.context_requests import lens_checks_section
from sentinel.discovery import detect_gaps

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_LENSES = REPO_ROOT / "sentinel" / "lenses"


class LensRegistryShapeTests(unittest.TestCase):
    def test_registry_loads_and_is_wellformed(self):
        checks = lens_registry.load_lens_checks()
        self.assertGreaterEqual(len(checks), 20)
        ids = [c["id"] for c in checks]
        self.assertEqual(len(ids), len(set(ids)), "duplicate gap ids across lens files")
        for c in checks:
            self.assertIn(c["rule"], lens_registry.VALID_RULES, c["id"])
            self.assertIn(c.get("evidence_scope", "source"), lens_registry.VALID_SCOPES, c["id"])
            self.assertTrue(c["description"], c["id"])
            self.assertIn(c["severity"], {"critical", "high", "medium", "low"}, c["id"])

    def test_known_checks_route_to_expected_lens(self):
        self.assertTrue(any(c["id"] == "GAP-OBJECTIVE" and c["lens"] == "business"
                            for c in lens_registry.load_lens_checks()))
        self.assertTrue(any(c["id"] == "GAP-DESIGN-FLOW" and c["lens"] == "design"
                            for c in lens_registry.load_lens_checks()))


class AddCheckWithoutPythonTests(unittest.TestCase):
    """Edit only a lens file; the new check must surface in both surfaces."""

    def setUp(self):
        self.tmp = Path(self._make_temp())
        shutil.copytree(REAL_LENSES, self.tmp / "lenses")
        # Add a brand-new check to the technical lens by editing only JSON.
        tech_path = self.tmp / "lenses" / "technical.json"
        data = json.loads(tech_path.read_text(encoding="utf-8"))
        data["checks"].append({
            "id": "GAP-OBSERVABILITY-RUNBOOK",
            "severity": "medium",
            "rule": "absent_tokens",
            "evidence_scope": "technical",
            "description": "Runbook and on-call ownership for the new surface are not explicit.",
            "tokens": ["runbook", "on-call", "oncall", "guardia"],
            "why": "Sin runbook ni owner de guardia, una falla en produccion no tiene dueno.",
        })
        tech_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        lens_registry.clear_cache()

    def _make_temp(self):
        import tempfile
        self._td = tempfile.mkdtemp(prefix="lens_test_")
        return self._td

    def tearDown(self):
        shutil.rmtree(self._td, ignore_errors=True)
        lens_registry.clear_cache()

    def test_new_check_fires_in_detect_gaps(self):
        # A requirement that never mentions runbook/on-call must now open the gap.
        text = "We need an API that syncs orders between two systems."
        gaps = {g["id"] for g in detect_gaps(text, lenses_dir=self.tmp / "lenses")}
        self.assertIn("GAP-OBSERVABILITY-RUNBOOK", gaps)

    def test_new_check_appears_in_context_request(self):
        original = lens_registry.LENSES_DIR
        try:
            lens_registry.LENSES_DIR = self.tmp / "lenses"
            lens_registry.clear_cache()
            section = lens_checks_section("technology", "en")
            self.assertIn("GAP-OBSERVABILITY-RUNBOOK", section)
        finally:
            lens_registry.LENSES_DIR = original
            lens_registry.clear_cache()


if __name__ == "__main__":
    unittest.main()
