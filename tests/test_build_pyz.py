from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from sentinel.build import build_pyz


ROOT = Path(__file__).resolve().parents[1]

PORTABLE_ROOT_FILES = (
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "kilo.jsonc",
)

PORTABLE_ROOT_DIRS = (
    ".agents",
    ".claude",
    ".codex",
    ".kilo",
    "input",
    "installers",
    "sentinel",
    "user_guide",
    "workspaces/_template",
)


class BuildPyzTest(unittest.TestCase):
    def test_builds_zipapp_and_runs_doctor_from_clean_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            target = build_pyz(temp / "sentinel.pyz")

            self.assertTrue(target.exists())
            with zipfile.ZipFile(target) as archive:
                names = archive.namelist()
            self.assertIn("__main__.py", names)
            self.assertIn("sentinel/cli.py", names)
            self.assertIn("sentinel/templates/commands_manifest.json", names)
            self.assertIn("sentinel/slicing/backlog_slicing_model.json", names)
            self.assertFalse(any("__pycache__" in name for name in names))

            pyz_result = subprocess.run(
                [sys.executable, str(target), "/doctor", "--root", str(ROOT)],
                cwd=temp,
                text=True,
                capture_output=True,
                timeout=60,
                check=True,
            )
            module_result = subprocess.run(
                [sys.executable, "-m", "sentinel", "/doctor", "--root", str(ROOT)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=60,
                check=True,
            )

        pyz_payload = json.loads(pyz_result.stdout)
        module_payload = json.loads(module_result.stdout)
        self.assertEqual("PASS", pyz_payload["verdict"])
        self.assertEqual(module_payload["commands"], pyz_payload["commands"])
        self.assertEqual(module_payload["summary"]["failures"], pyz_payload["summary"]["failures"])

    def test_zipapp_doctor_passes_against_clean_framework_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            portable_root = temp / "portable-root"
            runner = temp / "runner"
            runner.mkdir()
            _copy_portable_root(portable_root)
            target = build_pyz(portable_root / "dist" / "sentinel.pyz")

            self.assertFalse((portable_root / ".git").exists())
            self.assertFalse((portable_root / ".venv").exists())
            self.assertTrue(target.exists())

            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["PYTHONNOUSERSITE"] = "1"
            result = subprocess.run(
                [sys.executable, str(target), "/doctor", "--root", str(portable_root)],
                cwd=runner,
                env=env,
                text=True,
                capture_output=True,
                timeout=60,
                check=True,
            )

        payload = json.loads(result.stdout)
        checks = {check["name"]: check for check in payload["checks"]}
        self.assertEqual("PASS", payload["verdict"])
        self.assertEqual(str(portable_root.resolve()), payload["root"])
        self.assertEqual(0, payload["summary"]["failures"])
        self.assertEqual("PASS", checks["stdlib purity"]["status"])
        self.assertEqual("PASS", checks["command adapter manifest"]["status"])
        self.assertEqual("PASS", checks["repo write access"]["status"])
        if checks["memory backend mode"]["status"] == "WARN":
            self.assertIn("json-hybrid", checks["memory backend mode"]["detail"])


def _copy_portable_root(destination: Path) -> None:
    destination.mkdir(parents=True)
    for relative in PORTABLE_ROOT_FILES:
        shutil.copy2(ROOT / relative, destination / relative)
    for relative in PORTABLE_ROOT_DIRS:
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, ignore=_ignore_portable_copy_artifacts)


def _ignore_portable_copy_artifacts(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in {"__pycache__", ".pytest_cache", ".mypy_cache", "dist", ".venv"}
        or name.endswith((".pyc", ".pyo"))
    }


if __name__ == "__main__":
    unittest.main()
