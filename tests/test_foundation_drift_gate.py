import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.drift import foundation_drift_warnings, record_derived_source_fingerprint
from sentinel.generation import enforce_foundation_drift_gate
from sentinel.workspace import workspace_path


class FoundationDriftGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "FDG"]), 0)
        self.base = workspace_path("FDG")
        self.brief = self.base / "02_requirements" / "project-brief.md"
        self.reqs = self.base / "02_requirements" / "requirements.md"
        self.brief.parent.mkdir(parents=True, exist_ok=True)
        self.brief.write_text("# Brief\n\nObjective: reduce churn.\n", encoding="utf-8")
        self.reqs.write_text("# Requirements\n\nREQ-EARS-001: the system shall notify.\n", encoding="utf-8")

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _drift_specs(self) -> None:
        record_derived_source_fingerprint("FDG", "specs")
        self.brief.write_text("# Brief\n\nObjective changed materially.\n", encoding="utf-8")

    def test_no_registry_means_no_warning(self):
        self.assertEqual(foundation_drift_warnings("FDG", "specs"), [])
        self.assertEqual(foundation_drift_warnings("FDG", "backlog"), [])

    def test_unchanged_foundation_produces_no_warning(self):
        record_derived_source_fingerprint("FDG", "specs")
        self.assertEqual(foundation_drift_warnings("FDG", "specs"), [])

    def test_stale_foundation_warns_for_specs_and_backlog_phases(self):
        self._drift_specs()
        specs_w = foundation_drift_warnings("FDG", "specs")
        backlog_w = foundation_drift_warnings("FDG", "backlog")
        self.assertEqual(len(specs_w), 1)
        self.assertIn("STALE", specs_w[0])
        self.assertIn("`specs`", specs_w[0])
        self.assertIn("project-brief.md", specs_w[0])
        # /backlog builds on specs, so a stale specs is surfaced there too.
        self.assertTrue(any("`specs`" in w for w in backlog_w))

    def test_soft_gate_returns_warnings_without_raising(self):
        self._drift_specs()
        warnings = enforce_foundation_drift_gate("FDG", "specs", {})
        self.assertEqual(len(warnings), 1)

    def test_strict_gate_blocks(self):
        self._drift_specs()
        with self.assertRaises(RuntimeError) as ctx:
            enforce_foundation_drift_gate("FDG", "specs", {"drift_gate": {"strict": True}})
        self.assertIn("drift_gate.strict", str(ctx.exception))

    def test_unknown_phase_never_warns(self):
        self._drift_specs()
        self.assertEqual(foundation_drift_warnings("FDG", "brief"), [])


if __name__ == "__main__":
    unittest.main()
