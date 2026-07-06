"""Guards for the shell launchers (IMP-171).

The PowerShell launcher must propagate the CLI exit code (BUG G1) and resolve
the repo root / .venv from the script location so it works from any cwd (G2).
The POSIX launcher must cd to the repo root before running. These are static
guards plus a behavioural check of sentinel.sh where a POSIX shell exists.
"""

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLERS = REPO_ROOT / "installers"


class LauncherStaticGuards(unittest.TestCase):
    def test_ps1_propagates_exit_code(self):
        text = (INSTALLERS / "sentinel.ps1").read_text(encoding="utf-8")
        self.assertIn(
            "exit $LASTEXITCODE",
            text,
            "sentinel.ps1 must propagate the CLI exit code (BUG G1)",
        )

    def test_ps1_resolves_from_script_root(self):
        text = (INSTALLERS / "sentinel.ps1").read_text(encoding="utf-8")
        self.assertIn(
            "$PSScriptRoot",
            text,
            "sentinel.ps1 must resolve the repo root from the script location, not cwd (G2)",
        )

    def test_sh_cds_to_repo_root(self):
        text = (INSTALLERS / "sentinel.sh").read_text(encoding="utf-8")
        self.assertIn("dirname", text)
        self.assertIn('cd -- "$REPO_ROOT"', text)


class ShLauncherBehavior(unittest.TestCase):
    """Behavioural check: the POSIX launcher, invoked from outside the repo root,
    still resolves the package and propagates a non-zero gate/error exit code."""

    def setUp(self):
        self.sh = shutil.which("sh")
        if not self.sh:
            self.skipTest("no POSIX shell available")

    def _run(self, args, cwd):
        env = dict(os.environ)
        # Use the current interpreter (which can import sentinel) so the launcher
        # does not depend on a specific python being on PATH.
        env["SENTINEL_PYTHON"] = sys.executable
        return subprocess.run(
            [self.sh, str(INSTALLERS / "sentinel.sh"), *args],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_nonexistent_project_exits_nonzero_from_outside_root(self):
        result = self._run(["/status", "NO_EXISTE_LAUNCHER_TEST"], cwd=REPO_ROOT.parent)
        self.assertNotEqual(
            result.returncode,
            0,
            f"launcher swallowed the gate exit code; stdout={result.stdout!r} stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
