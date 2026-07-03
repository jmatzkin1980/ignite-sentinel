import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.core.state import read_state
from sentinel.health import out_of_cli_edit_warnings, run_health
from sentinel.protocols import snapshot_governed_artifact_hashes
from sentinel.workspace import workspace_path


class ArtifactChecksumUnitTests(unittest.TestCase):
    def test_no_registry_means_no_warning(self):
        # Back-compat: a workspace generated before IMP-147 has no
        # artifact_hashes registry, so the check must stay silent.
        self.assertEqual(out_of_cli_edit_warnings("MISSING", Path("nowhere")), [])


class ArtifactChecksumFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        source = self.temp / "request.md"
        source.write_text(
            "Need a read-only dashboard for support leads. Acceptance: leads see queue risk before standup.",
            encoding="utf-8",
        )
        self.assertEqual(main(["init", "CHK"]), 0)
        self.assertEqual(main(["ingest", "CHK", "--source", str(source)]), 0)
        self.gaps = workspace_path("CHK") / "01_discovery" / "gaps.md"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp)

    def test_mutating_command_snapshots_governed_hashes(self):
        registered = read_state("CHK").get("artifact_hashes", {})
        self.assertIn("01_discovery/gaps.md", registered)
        # The snapshot equals a fresh recompute right after CLI generation.
        current = snapshot_governed_artifact_hashes("CHK")
        self.assertEqual(current["01_discovery/gaps.md"], registered["01_discovery/gaps.md"])

    def test_clean_workspace_produces_no_out_of_cli_warning(self):
        warnings = run_health("CHK")["warnings"]
        self.assertFalse(any("edited outside the CLI" in w for w in warnings))

    def test_hand_edit_is_flagged_without_blocking(self):
        self.gaps.write_text(self.gaps.read_text(encoding="utf-8") + "\n<!-- hand edit -->\n", encoding="utf-8")
        report = run_health("CHK")
        offending = [w for w in report["warnings"] if "edited outside the CLI" in w]
        self.assertEqual(len(offending), 1)
        self.assertIn("01_discovery/gaps.md", offending[0])
        # It only warns; the verdict is not driven DIRTY by an out-of-CLI edit.
        self.assertNotIn("edited outside the CLI", " ".join(report.get("findings", [])))

    def test_cli_regeneration_refreshes_snapshot_and_clears_warning(self):
        self.gaps.write_text(self.gaps.read_text(encoding="utf-8") + "\n<!-- hand edit -->\n", encoding="utf-8")
        self.assertTrue(any("edited outside the CLI" in w for w in run_health("CHK")["warnings"]))
        # A mutating command re-snapshots the governed registry.
        self.assertEqual(main(["gaps", "CHK"]), 0)
        self.assertFalse(any("edited outside the CLI" in w for w in run_health("CHK")["warnings"]))


if __name__ == "__main__":
    unittest.main()
