"""Run the unit suite by CI tier (IMP-246), optionally in parallel (IMP-309).

    python tools/run_tests.py --tier fast   # every module except tests/slow_modules.txt
    python tools/run_tests.py --tier full   # the whole suite (same as unittest discover -s tests)
    python tools/run_tests.py --tier full --slowest 10   # ...then the 10 slowest modules
    python tools/run_tests.py --tier full --jobs auto --slowest 10   # verify.ps1 / verify.sh

The slow set is an explicit list (``tests/slow_modules.txt``), chosen from measured
durations (``tools/time_tests.py``), so the fast tier is reproducible and reviewable.

``--jobs N`` runs whole modules in N worker processes. Modules are the unit because
a module's fixtures (setUpModule, setUpClass) and its working-directory changes are
process state; inside one worker, modules run one after another exactly as in a
serial run. The slow list goes first, so the longest modules do not start last.
Each worker's own stdout (the CLI output many tests print) is discarded; failures
come back with their tracebacks.

Stdlib only. Exit code 0 only when every selected test passes.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
SLOW_LIST = TESTS / "slow_modules.txt"


def slow_module_order() -> list[str]:
    """The slow list in its file order (slowest first)."""
    if not SLOW_LIST.is_file():
        return []
    names: list[str] = []
    for line in SLOW_LIST.read_text(encoding="utf-8").splitlines():
        name = line.split("#", 1)[0].strip()
        if name and name not in names:
            names.append(name)
    return names


def slow_modules() -> set[str]:
    return set(slow_module_order())


def selected_modules(tier: str) -> list[str]:
    modules = sorted(path.stem for path in TESTS.glob("test_*.py"))
    if tier == "full":
        return modules
    slow = slow_modules()
    unknown = sorted(slow - set(modules))
    if unknown:
        raise SystemExit(f"tests/slow_modules.txt names modules that do not exist: {', '.join(unknown)}")
    return [name for name in modules if name not in slow]


def schedule(modules: list[str], slow_first: list[str]) -> list[str]:
    """Longest first: the slow list in its order, then the rest alphabetically."""
    chosen = set(modules)
    head = [name for name in slow_first if name in chosen]
    return head + [name for name in modules if name not in set(head)]


class TimedResult(unittest.TextTestResult):
    """Attributes the time between two finished tests (fixtures included) to the later test's module."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_seconds: dict[str, float] = {}
        self.module_tests: dict[str, int] = {}
        self._mark = time.perf_counter()

    def stopTest(self, test):
        super().stopTest(test)
        now = time.perf_counter()
        module = type(test).__module__
        self.module_seconds[module] = self.module_seconds.get(module, 0.0) + (now - self._mark)
        self.module_tests[module] = self.module_tests.get(module, 0) + 1
        self._mark = now


def slowest_report(result, top: int) -> str:
    """IMP-305: where the suite's time goes, so a jump shows in the PR that causes it.

    `result` is anything with `module_seconds` and `module_tests` mappings.
    """
    total = sum(result.module_seconds.values()) or 1.0
    slowest = sorted(result.module_seconds.items(), key=lambda item: -item[1])[:top]
    lines = [f"Slowest {len(slowest)} test modules (of {len(result.module_seconds)}):"]
    for module, seconds in slowest:
        lines.append(f"  {seconds:7.1f}s  {100 * seconds / total:4.1f}%  {result.module_tests[module]:4d} tests  {module}")
    return "\n".join(lines)


# --- parallel run (IMP-309) -------------------------------------------------------


def _worker_init() -> None:
    sys.path.insert(0, str(TESTS))
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 - lives as long as the worker


def run_module(name: str) -> dict:
    """Run one test module in this process; return a picklable summary."""
    stream = io.StringIO()
    start = time.perf_counter()
    try:
        suite = unittest.defaultTestLoader.loadTestsFromName(name)
    except Exception as exc:  # an import error is a failure of the module, not of the run
        return {"module": name, "run": 0, "seconds": 0.0, "skipped": 0, "tests": {},
                "problems": [("ERROR", name, f"{type(exc).__name__}: {exc}")]}
    runner = unittest.TextTestRunner(stream=stream, verbosity=0, resultclass=TimedResult)
    result = runner.run(suite)
    problems = [("FAIL", test.id(), trace) for test, trace in result.failures]
    problems += [("ERROR", getattr(test, "id", lambda: str(test))(), trace) for test, trace in result.errors]
    problems += [("FAIL", test.id(), "unexpected success") for test in result.unexpectedSuccesses]
    return {
        "module": name,
        "run": result.testsRun,
        "seconds": time.perf_counter() - start,
        "skipped": len(result.skipped),
        "module_seconds": result.module_seconds,
        "module_tests": result.module_tests,
        "problems": problems,
    }


class MergedResult:
    """The per-module summaries of a parallel run, added up."""

    def __init__(self, summaries: list[dict]):
        self.summaries = summaries
        self.run = sum(item["run"] for item in summaries)
        self.skipped = sum(item["skipped"] for item in summaries)
        self.problems = [problem for item in summaries for problem in item["problems"]]
        self.module_seconds: dict[str, float] = {}
        self.module_tests: dict[str, int] = {}
        for item in summaries:
            for module, seconds in (item.get("module_seconds") or {item["module"]: item["seconds"]}).items():
                self.module_seconds[module] = self.module_seconds.get(module, 0.0) + seconds
            for module, count in (item.get("module_tests") or {item["module"]: item["run"]}).items():
                self.module_tests[module] = self.module_tests.get(module, 0) + count

    def was_successful(self) -> bool:
        return not self.problems

    def report(self, elapsed: float) -> str:
        """The same closing lines as unittest's runner, so tooling that reads them keeps working."""
        separator = "=" * 70
        lines: list[str] = []
        for kind, test_id, trace in self.problems:
            lines += [separator, f"{kind}: {test_id}", "-" * 70, trace.rstrip()]
        lines += ["-" * 70, f"Ran {self.run} tests in {elapsed:.3f}s", ""]
        failures = sum(1 for kind, _, _ in self.problems if kind == "FAIL")
        errors = len(self.problems) - failures
        extras = [f"failures={failures}"] * bool(failures) + [f"errors={errors}"] * bool(errors)
        extras += [f"skipped={self.skipped}"] * bool(self.skipped)
        status = "FAILED" if self.problems else "OK"
        lines.append(f"{status} ({', '.join(extras)})" if extras else status)
        return "\n".join(lines)


def resolve_jobs(value: str) -> int:
    if value == "auto":
        return max(1, os.cpu_count() or 1)
    jobs = int(value)
    if jobs < 1:
        raise SystemExit("--jobs must be a positive number or 'auto'")
    return jobs


def run_parallel(modules: list[str], jobs: int) -> MergedResult:
    import multiprocessing

    ordered = schedule(modules, slow_module_order())
    with multiprocessing.get_context("spawn").Pool(processes=jobs, initializer=_worker_init) as pool:
        summaries = list(pool.imap_unordered(run_module, ordered, chunksize=1))
    return MergedResult(summaries)


def main(argv: list[str] | None = None) -> int:
    # A failure message with a non-ASCII character (an arrow, an accent) used to crash the
    # final report on a Windows cp1252 console and hide which test failed.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tier", choices=("fast", "full"), default="fast")
    parser.add_argument("--slowest", type=int, default=0, metavar="N", help="list the N slowest test modules at the end")
    parser.add_argument("--jobs", default="1", metavar="N", help="worker processes, or 'auto' for one per CPU (default 1)")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(TESTS))
    sys.path.insert(0, str(ROOT))
    modules = selected_modules(args.tier)
    jobs = resolve_jobs(args.jobs)
    print(f"tier={args.tier}: {len(modules)} modules, jobs={jobs}", flush=True)
    if jobs == 1:
        suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
        result = unittest.TextTestRunner(verbosity=1, resultclass=TimedResult).run(suite)
        if args.slowest:
            print("\n" + slowest_report(result, args.slowest), flush=True)
        return 0 if result.wasSuccessful() else 1
    start = time.perf_counter()
    merged = run_parallel(modules, jobs)
    print(merged.report(time.perf_counter() - start), flush=True)
    if args.slowest:
        print("\n" + slowest_report(merged, args.slowest), flush=True)
    return 0 if merged.was_successful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
