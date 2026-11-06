"""IMP-242: the non-editable wheel works outside the clone.

Slow and opt-in (``SENTINEL_SLOW=1``): it builds the wheel (build isolation
downloads setuptools, so it needs network), installs it into a clean venv and
runs ``/init`` and ``/status`` from a directory with no ``workspaces/``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_INPUTS = ("pyproject.toml", "README.md", "LICENSE")


def _venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


@unittest.skipUnless(os.environ.get("SENTINEL_SLOW") == "1", "slow: builds and installs the wheel")
class WheelInstallTests(unittest.TestCase):
    def _run(self, step: str, command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        # A PYTHONPATH pointing at the clone would let the venv import the repo's
        # sentinel/ instead of the wheel's, and a broken wheel would pass.
        env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
        env["PYTHONNOUSERSITE"] = "1"
        result = subprocess.run(
            [str(part) for part in command],
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )
        self.assertEqual(
            0,
            result.returncode,
            f"{step} failed (exit {result.returncode})\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def test_wheel_installs_and_runs_outside_the_repo(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        tmp = Path(temp.name)

        # Build from a pristine copy: an in-tree build would leave build/ in the
        # repo, and a stale build/lib could mask a package missing from the config.
        src = tmp / "src"
        src.mkdir()
        for name in BUILD_INPUTS:
            shutil.copy2(ROOT / name, src / name)
        shutil.copytree(ROOT / "sentinel", src / "sentinel", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        wheel_dir = tmp / "wh"
        self._run("pip wheel", [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", wheel_dir, src])
        wheels = sorted(wheel_dir.glob("*.whl"))
        self.assertEqual(1, len(wheels), f"expected one wheel, got {wheels}")

        venv = tmp / "venv"
        self._run("venv", [sys.executable, "-m", "venv", venv])
        python = _venv_python(venv)
        self._run("pip install", [python, "-m", "pip", "install", "--no-deps", "--no-index", wheels[0]])

        run_dir = tmp / "run"
        run_dir.mkdir()
        self._run("/init", [python, "-m", "sentinel", "/init", "WHEELT"], cwd=run_dir)
        self._run("/status", [python, "-m", "sentinel", "/status", "WHEELT"], cwd=run_dir)

        origin = self._run(
            "import origin", [python, "-c", "import sentinel; print(sentinel.__file__)"], cwd=run_dir
        ).stdout.strip()
        self.assertTrue(
            Path(origin).resolve().is_relative_to(venv.resolve()),
            f"sentinel imported from {origin}, not from the wheel installed in {venv}",
        )
        self.assertTrue((run_dir / "workspaces" / "WHEELT" / "state.json").is_file())


if __name__ == "__main__":
    unittest.main()
