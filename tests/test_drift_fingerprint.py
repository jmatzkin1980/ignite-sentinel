import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.core.state import read_state
from sentinel.drift import (
    DERIVED_SOURCE_MAP,
    record_derived_source_fingerprint,
    source_fingerprint,
)
from sentinel.workspace import workspace_path


class DriftFingerprintTests(unittest.TestCase):
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

    def test_absent_source_is_recorded_as_none(self):
        fp = source_fingerprint("DRIFT", ("03_specs/specs.md",))
        self.assertEqual(fp, {"03_specs/specs.md": None})

    def test_recording_snapshots_present_source_hashes(self):
        fp = record_derived_source_fingerprint("DRIFT", "specs")
        for rel in DERIVED_SOURCE_MAP["specs"]:
            self.assertIn(rel, fp)
        self.assertIsNotNone(fp["02_requirements/project-brief.md"])
        self.assertIsNotNone(fp["02_requirements/requirements.md"])
        stored = read_state("DRIFT")["derived_source_fingerprints"]["specs"]
        self.assertEqual(stored, fp)

    def test_recording_is_stable_when_source_unchanged(self):
        first = record_derived_source_fingerprint("DRIFT", "specs")
        second = record_derived_source_fingerprint("DRIFT", "specs")
        self.assertEqual(first, second)

    def test_changed_source_yields_a_different_fingerprint(self):
        first = record_derived_source_fingerprint("DRIFT", "specs")
        self.brief.write_text("# Brief\n\nObjective: reduce churn AND increase NPS.\n", encoding="utf-8")
        second = record_derived_source_fingerprint("DRIFT", "specs")
        self.assertNotEqual(
            first["02_requirements/project-brief.md"],
            second["02_requirements/project-brief.md"],
        )

    def test_recording_one_derived_preserves_another(self):
        (self.base / "03_specs").mkdir(parents=True, exist_ok=True)
        (self.base / "03_specs" / "specs.md").write_text("# Specs\n", encoding="utf-8")
        record_derived_source_fingerprint("DRIFT", "specs")
        record_derived_source_fingerprint("DRIFT", "backlog")
        registry = read_state("DRIFT")["derived_source_fingerprints"]
        self.assertIn("specs", registry)
        self.assertIn("backlog", registry)
        self.assertIsNotNone(registry["backlog"]["03_specs/specs.md"])


if __name__ == "__main__":
    unittest.main()
