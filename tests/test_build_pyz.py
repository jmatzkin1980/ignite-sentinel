from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from sentinel.build import build_pyz


ROOT = Path(__file__).resolve().parents[1]


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


if __name__ == "__main__":
    unittest.main()
