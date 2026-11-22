"""IMP-317: outside a framework clone, /doctor must not suggest `pip install -e .[extra]`.

That command installs the clone's own project; in a plugin, wheel or .pyz project folder there
is no project to install, so the hint has to name the packages instead.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from sentinel.doctor import runtime_hint, run_doctor


class DoctorRuntimeInstallHintsTest(unittest.TestCase):
    def test_hint_names_the_packages(self):
        check = {"name": "x", "status": "WARN", "detail": (
            "Enable vector retrieval with `python -m pip install -e .[memory]`. "
            "Models: `python -m pip install -e .[memory-semantic]`. "
            "MCP: `python -m pip install -e .[mcp]`."
        )}
        detail = runtime_hint(check)["detail"]
        self.assertNotIn("-e .", detail)
        py = (f'& "{sys.executable}"' if os.name == "nt" else f'"{sys.executable}"') + " -m pip install"  # IMP-398: the interpreter Sentinel runs with
        self.assertIn(f"`{py} lancedb`", detail)
        self.assertIn(f"`{py} model2vec sentence-transformers`", detail)
        self.assertIn(f'`{py} "mcp>=1.2,<3"`', detail)
        self.assertIn("same Python that runs Sentinel", detail)

    def test_check_without_a_hint_is_unchanged(self):
        check = {"name": "x", "status": "PASS", "detail": "all good"}
        self.assertEqual(runtime_hint(check), check)

    def test_runtime_doctor_never_suggests_an_editable_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_doctor(Path(tmp))
        self.assertEqual(result["mode"], "runtime")
        for check in result["checks"]:
            with self.subTest(check=check["name"]):
                self.assertNotIn("-e .", check["detail"])


if __name__ == "__main__":
    unittest.main()
