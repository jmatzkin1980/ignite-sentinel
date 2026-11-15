"""IMP-305: tools/run_tests.py lists where the suite's time goes."""
from __future__ import annotations

import importlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tool():
    # Imported by its real name: worker processes (spawn) re-import the module that
    # defines the functions they run, so it must be importable from sys.path.
    if str(ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools"))
    return importlib.import_module("run_tests")


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


class ParallelRunTests(unittest.TestCase):
    """IMP-309: --jobs runs whole modules in worker processes and adds the results up."""

    def test_the_slow_list_goes_first_in_its_order(self) -> None:
        tool = _tool()
        order = tool.schedule(["test_a", "test_b", "test_c", "test_slow1", "test_slow2"], ["test_slow2", "test_slow1", "test_gone"])
        self.assertEqual(order, ["test_slow2", "test_slow1", "test_a", "test_b", "test_c"])

    def test_the_merged_report_keeps_unittest_closing_lines(self) -> None:
        tool = _tool()
        ok = tool.MergedResult([
            {"module": "test_a", "run": 3, "seconds": 1.0, "skipped": 1, "problems": []},
            {"module": "test_b", "run": 2, "seconds": 2.0, "skipped": 0, "problems": []},
        ])
        self.assertTrue(ok.was_successful())
        self.assertTrue(ok.report(3.5).endswith("Ran 5 tests in 3.500s\n\nOK (skipped=1)"))
        self.assertEqual(ok.module_tests, {"test_a": 3, "test_b": 2})
        failed = tool.MergedResult([
            {"module": "test_a", "run": 2, "seconds": 1.0, "skipped": 0,
             "problems": [("FAIL", "test_a.T.test_x", "Traceback\nAssertionError: boom"), ("ERROR", "test_a.T.test_y", "Traceback")]},
        ])
        report = failed.report(1.0)
        self.assertFalse(failed.was_successful())
        self.assertIn("FAIL: test_a.T.test_x", report)
        self.assertIn("AssertionError: boom", report)
        self.assertTrue(report.endswith("FAILED (failures=1, errors=1)"))

    def test_jobs_auto_is_one_per_cpu_and_zero_is_refused(self) -> None:
        tool = _tool()
        self.assertGreaterEqual(tool.resolve_jobs("auto"), 1)
        self.assertEqual(tool.resolve_jobs("3"), 3)
        with self.assertRaises(SystemExit):
            tool.resolve_jobs("0")

    def test_a_real_parallel_run_counts_every_test(self) -> None:
        import multiprocessing

        if multiprocessing.current_process().daemon:
            self.skipTest("already inside a --jobs worker, which cannot start processes of its own")
        tool = _tool()
        modules = ["test_prioritization_reference", "test_intake_triage_skill"]
        serial = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromNames(modules))
        merged = tool.run_parallel(modules, 2)
        self.assertTrue(merged.was_successful(), merged.problems)
        self.assertEqual(merged.run, serial.testsRun)
        self.assertEqual(set(merged.module_tests), set(modules))


if __name__ == "__main__":
    unittest.main()
