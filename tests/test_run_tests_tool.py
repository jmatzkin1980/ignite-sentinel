"""IMP-305: tools/run_tests.py lists where the suite's time goes."""
from __future__ import annotations

import importlib.util
import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location("run_tests_tool", ROOT / "tools" / "run_tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Fast(unittest.TestCase):
    def test_one(self) -> None:
        pass

    def test_two(self) -> None:
        pass


class SlowestReportTests(unittest.TestCase):
    def test_the_report_names_each_module_with_its_tests(self) -> None:
        tool = _tool()
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(_Fast)
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=tool.TimedResult).run(suite)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.module_tests, {__name__: 2})
        report = tool.slowest_report(result, 10)
        self.assertIn("Slowest 1 test modules (of 1):", report)
        self.assertIn(f"2 tests  {__name__}", report)

    def test_slow_modules_list_names_existing_modules(self) -> None:
        tool = _tool()
        self.assertTrue(tool.selected_modules("fast"))  # raises if the slow list names a missing module


if __name__ == "__main__":
    unittest.main()
