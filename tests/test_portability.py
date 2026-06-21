from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel.doctor import stdlib_purity_check
from sentinel.portability import stdlib_purity_violations


ROOT = Path(__file__).resolve().parents[1]


class StdlibPurityTest(unittest.TestCase):
    def test_runtime_has_no_unguarded_third_party_imports(self) -> None:
        violations = stdlib_purity_violations(ROOT / "sentinel")

        self.assertEqual([], [violation.format() for violation in violations])

    def test_detects_unguarded_third_party_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Path(temp_dir) / "sentinel"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "bad.py").write_text("import requests\n", encoding="utf-8")

            violations = stdlib_purity_violations(package)

        self.assertEqual(1, len(violations))
        self.assertEqual("requests", violations[0].module)
        self.assertIn("not in the optional allowlist", violations[0].reason)

    def test_allows_local_imports_and_guarded_optional_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Path(temp_dir) / "sentinel"
            nested = package / "backlog"
            nested.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "cli.py").write_text("COMMANDS = {}\n", encoding="utf-8")
            (nested / "__init__.py").write_text("", encoding="utf-8")
            (nested / "gates.py").write_text("VALUE = 1\n", encoding="utf-8")
            (nested / "hooks.py").write_text(
                "\n".join(
                    [
                        "from gates import VALUE",
                        "from backlog.gates import VALUE as OTHER_VALUE",
                        "from sentinel.cli import COMMANDS",
                        "try:",
                        "    import lancedb",
                        "except ImportError:",
                        "    lancedb = None",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            violations = stdlib_purity_violations(package)

        self.assertEqual([], [violation.format() for violation in violations])

    def test_rejects_unknown_third_party_even_when_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Path(temp_dir) / "sentinel"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "bad.py").write_text(
                "\n".join(
                    [
                        "try:",
                        "    import requests",
                        "except ImportError:",
                        "    requests = None",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            violations = stdlib_purity_violations(package)

        self.assertEqual(1, len(violations))
        self.assertEqual("requests", violations[0].module)
        self.assertIn("not in the optional allowlist", violations[0].reason)

    def test_doctor_stdlib_purity_check_reports_failure_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package = root / "sentinel"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "bad.py").write_text("import requests\n", encoding="utf-8")

            check = stdlib_purity_check(root)

        self.assertEqual("stdlib purity", check["name"])
        self.assertEqual("FAIL", check["status"])
        self.assertIn("requests", check["detail"])


if __name__ == "__main__":
    unittest.main()
