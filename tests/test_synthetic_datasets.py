"""IMP-196: synthetic handoff datasets — non-governed marker + negative citation guard."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel.synthetic_datasets import (
    SYNTHETIC_MARKER,
    SYNTHETIC_RELATIVE_DIR,
    GOVERNED_LIFECYCLE_DIRS,
    references_synthetic,
    synthetic_dir,
)
from sentinel.validation import check_no_synthetic_citation


class SyntheticContractTests(unittest.TestCase):
    def test_synthetic_area_is_outside_the_governed_lifecycle_tree(self):
        # The whole point: synthetic data must not live in a dir any evidence scan reads.
        top_segment = SYNTHETIC_RELATIVE_DIR.split("/", 1)[0]
        self.assertNotIn(SYNTHETIC_RELATIVE_DIR, GOVERNED_LIFECYCLE_DIRS)
        self.assertNotIn(top_segment, GOVERNED_LIFECYCLE_DIRS)

    def test_marker_present(self):
        self.assertIn("SYNTHETIC", SYNTHETIC_MARKER)
        self.assertIn("not evidence", SYNTHETIC_MARKER)

    def test_synthetic_dir_joins_under_base(self):
        base = Path("/tmp/ws")
        self.assertEqual(synthetic_dir(base).as_posix(), "/tmp/ws/08_context_packs/synthetic")


class ReferencesSyntheticTests(unittest.TestCase):
    def test_detects_posix_and_windows_pointers(self):
        self.assertTrue(references_synthetic("08_context_packs/synthetic/customers.csv"))
        self.assertTrue(references_synthetic("08_context_packs\\synthetic\\orders.json"))
        self.assertTrue(references_synthetic("See 08_Context_Packs/Synthetic/seed.sql for data."))

    def test_ignores_governed_and_empty_pointers(self):
        self.assertFalse(references_synthetic(""))
        self.assertFalse(references_synthetic("00_raw/00_client_requirement/input.md"))
        self.assertFalse(references_synthetic("08_context_packs/exports/gaps.md"))


class NoSyntheticCitationGuardTests(unittest.TestCase):
    def _run(self, base: Path):
        checks: list[dict[str, object]] = []
        warnings: list[dict[str, str]] = []
        check_no_synthetic_citation("demo", base, checks, warnings)
        entry = next(c for c in checks if c["id"] == "no_synthetic_citation")
        return entry, warnings

    def test_clean_project_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            unit = base / "03_specs" / "units"
            unit.mkdir(parents=True)
            (unit / "SPEC-U-001.md").write_text(
                "sources: 00_raw/00_client_requirement/input.md\n", encoding="utf-8"
            )
            entry, warnings = self._run(base)
            self.assertEqual(entry["status"], "PASS")
            self.assertEqual(warnings, [])

    def test_citation_to_synthetic_area_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            unit = base / "03_specs" / "units"
            unit.mkdir(parents=True)
            (unit / "SPEC-U-002.md").write_text(
                "Source: 08_context_packs/synthetic/customers.csv\n", encoding="utf-8"
            )
            entry, warnings = self._run(base)
            self.assertEqual(entry["status"], "WARN")
            self.assertEqual(entry["issues"], 1)
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0]["check"], "synthetic_citation")
            self.assertIn("SPEC-U-002.md", warnings[0]["artifact"])


if __name__ == "__main__":
    unittest.main()
