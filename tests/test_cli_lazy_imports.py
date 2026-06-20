import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliLazyImportTests(unittest.TestCase):
    def test_cli_import_does_not_load_heavy_command_handlers(self) -> None:
        code = """
import json
import sys
import sentinel.cli
names = ["sentinel.doctor", "sentinel.generation", "importlib.metadata"]
print(json.dumps({name: name in sys.modules for name in names}))
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            text=True,
            capture_output=True,
            check=True,
        )
        loaded = json.loads(result.stdout)
        self.assertEqual(
            loaded,
            {"sentinel.doctor": False, "sentinel.generation": False, "importlib.metadata": False},
        )

    def test_status_command_does_not_import_unrelated_handlers(self) -> None:
        env = dict(os.environ)
        repo = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = repo + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        with tempfile.TemporaryDirectory(prefix="sentinel_cli_imports_") as temp:
            subprocess.run(
                [sys.executable, "-m", "sentinel", "init", "PERF"],
                cwd=temp,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            result = subprocess.run(
                [sys.executable, "-X", "importtime", "-m", "sentinel", "status", "PERF"],
                cwd=temp,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
        import_trace = result.stderr
        self.assertNotIn("sentinel.doctor", import_trace)
        self.assertNotIn("sentinel.generation", import_trace)
        self.assertNotIn("importlib.metadata", import_trace)


if __name__ == "__main__":
    unittest.main()
