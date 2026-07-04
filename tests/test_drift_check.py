import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.drift import derived_drift_warnings, record_derived_source_fingerprint
from sentinel.health import run_health
from sentinel.workspace import workspace_path


class DerivedDriftCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "DRIFT"]), 0)
        self.base = workspace_path("DRIFT")
        self.brief = self.base / "02_requirements" / "project-brief.md"
        self.reqs = self.base / "02_requirements" / "requirements.md"
        self.brief.parent.mkdir(parents=True, exist_ok=True)
        self.brief.write_text("# Brief\n\nObjective: reduce churn.\n", encoding="utf-8")
        self.reqs.write_text("# Requirements\n\nREQ-EARS-001: the system shall notify.\n", encoding="utf-8")

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_no_registry_means_no_warning(self):
        self.assertEqual(derived_drift_warnings("DRIFT"), [])

    def test_unchanged_source_produces_no_warning(self):
        record_derived_source_fingerprint("DRIFT", "specs")
        self.assertEqual(derived_drift_warnings("DRIFT"), [])

    def test_changed_source_is_flagged_and_names_the_source(self):
        record_derived_source_fingerprint("DRIFT", "specs")
        self.brief.write_text("# Brief\n\nObjective: reduce churn AND raise NPS.\n", encoding="utf-8")
        warnings = derived_drift_warnings("DRIFT")
        self.assertEqual(len(warnings), 1)
        self.assertIn("DRIFTED", warnings[0])
        self.assertIn("`specs`", warnings[0])
        self.assertIn("02_requirements/project-brief.md", warnings[0])
        self.assertIn("Nothing was rewritten", warnings[0])

    def test_drift_is_a_warning_not_a_blocking_finding(self):
        record_derived_source_fingerprint("DRIFT", "specs")
        self.brief.write_text("# Brief\n\nObjective changed materially.\n", encoding="utf-8")
        report = run_health("DRIFT")
        self.assertTrue(any("DRIFTED" in w for w in report["warnings"]))
        self.assertFalse(any("DRIFTED" in f for f in report["findings"]))
        # A source-drift signal never rewrites the derived artifact.
        self.assertEqual(
            self.brief.read_text(encoding="utf-8"),
            "# Brief\n\nObjective changed materially.\n",
        )


if __name__ == "__main__":
    unittest.main()
