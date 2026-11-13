"""IMP-26v / IMP-297 / IMP-298: the release series end to end, on synthetic multi-release fixtures.

Three fixtures, all labelled synthetic:
- `tests/fixtures/synthetic_series/` (IMP-26v): three sources (filing, approval,
  payment) and a chain of three functional releases.
- `tests/fixtures/synthetic_series_types/` (IMP-297): one source with five scope
  sentences (IMP-296) and a series with every kind the derivation must survive: a
  measuring spike with its DEC, functional releases, an interleaved `r2.1`, a
  conditional with its open gap and an integrator with its consumption table.
- `tests/fixtures/synthetic_series_more_types/` (IMP-298): the three remaining types,
  an already built release (its brief alone carries the `built` validation direction),
  an enabler with no unit of the brief and a segment cutover with its segment,
  eligibility model and switch.

The flow: v2 flow → `/split --assess` → `--propose` → validation → `--confirm`
(index and release briefs) → per release `specs`, `backlog` (with the slice plan),
`quality` and `/validate` VALID. Two full runs give identical release artifacts. The
validation's rejection of each seeded anti-pattern is covered by the partition evals
(`tests/evals/run_partition_evals.py`).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from sentinel.cli import main
from sentinel.memory import ContextBroker

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from golden_normalize import normalize  # noqa: E402

P = "CLAIMS"


@dataclass(frozen=True)
class Case:
    fixture: Path
    sources: tuple[str, ...]
    releases: tuple[str, ...]

    def compared(self) -> tuple[str, ...]:
        return ("02_requirements/series", *(f"02_requirements/{rid}" for rid in self.releases),
                *(f"{folder}/{rid}" for folder in ("03_specs", "04_backlog", "05_quality") for rid in self.releases))


CHAIN = Case(ROOT / "fixtures" / "synthetic_series", ("requirement.md", "approval_notes.md", "payment_notes.md"),
             ("r1", "r2", "r3"))
ALL_TYPES = Case(ROOT / "fixtures" / "synthetic_series_types", ("requirement.md",), ("r0", "r1", "r2", "r2.1", "r3", "r4"))
MORE_TYPES = Case(ROOT / "fixtures" / "synthetic_series_more_types", ("requirement.md",), ("r0", "r1", "r2", "r3"))


def _cli(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(argv)
    return code, out.getvalue()


def run_series(work: Path, case: Case = CHAIN) -> dict:
    """The whole flow in `work`; returns exit codes, validate verdicts and the normalized artifacts."""
    fx = case.fixture
    old = os.getcwd()
    os.chdir(work)
    result: dict = {"codes": {}, "verdicts": {}, "artifacts": {}}
    try:
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            steps = [["init", P]]
            steps += [["ingest", P, "--source", str(fx / name)] for name in case.sources]
            steps += [["gaps", P], ["resolve-gaps", P, "--source", str(fx / "gap_responses.md")], ["maturity", P],
                      ["brief", P, "--profile", "UI", "--genesis", "greenfield"], ["split", P, "--assess"],
                      ["split", P, "--propose", "--source", str(fx / "proposal.json")],
                      ["split", P, "--confirm", "--ba", "Synthetic BA", "--tech", "Synthetic team"]]
            for rid in case.releases:
                steps += [["specs", P, "--release", rid], ["backlog", P, "--release", rid], ["quality", P, "--release", rid]]
            for argv in steps:
                code, text = _cli(argv)
                result["codes"][" ".join(a for a in argv if not a.startswith(str(fx)))] = code
                if code:
                    result.setdefault("errors", []).append(f"{argv[0]} {' '.join(argv[2:])}: {text[-600:]}")
            for rid in case.releases:
                _, text = _cli(["validate", P, "--release", rid])
                verdict = json.loads(text[text.index("{"):])
                result["verdicts"][rid] = (verdict["verdict"], verdict["findings"])
            _, text = _cli(["validate", P])
            result["verdicts"]["project"] = json.loads(text[text.index("{"):])["verdict"]
        base = work / "workspaces" / P
        roots = {str(work.resolve()), work.resolve().as_posix(), str(work.resolve()).replace("\\", "\\\\")}
        for rel in case.compared():
            for path in sorted((base / rel).rglob("*")):
                if path.is_file() and path.suffix in {".md", ".json"}:
                    text = path.read_text(encoding="utf-8")
                    for root in sorted(roots, key=len, reverse=True):
                        text = text.replace(root, "[ROOT]")
                    result["artifacts"][path.relative_to(base).as_posix()] = normalize(text, P)
    finally:
        os.chdir(old)
    return result


class _SeriesEndToEnd:
    CASE: Case = CHAIN

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = [tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory()]
        cls.first = run_series(Path(cls.tmp[0].name), cls.CASE)
        cls.second = run_series(Path(cls.tmp[1].name), cls.CASE)

    @classmethod
    def tearDownClass(cls) -> None:
        for tmp in cls.tmp:
            tmp.cleanup()

    def test_fixture_is_labelled_synthetic(self) -> None:
        for path in self.CASE.fixture.iterdir():
            self.assertIn("synthetic", path.read_text(encoding="utf-8").lower(), path.name)

    def test_every_step_succeeds(self) -> None:
        self.assertEqual([k for k, v in self.first["codes"].items() if v], [], self.first.get("errors"))

    def test_series_is_compiled(self) -> None:
        artifacts = self.first["artifacts"]
        self.assertIn("02_requirements/series/index.md", artifacts)
        self.assertIn("02_requirements/series/release-guide.md", artifacts)
        for rid in self.CASE.releases:
            self.assertIn(f"02_requirements/{rid}/project-brief.md", artifacts)
            for rel in (f"03_specs/{rid}/prd.md", f"03_specs/{rid}/specs.md", f"04_backlog/{rid}/SLICE-PLAN.md",
                        f"05_quality/{rid}/backlog_readiness_audit.md"):
                self.assertIn(rel, artifacts)

    def test_each_release_validates(self) -> None:
        for rid in self.CASE.releases:
            self.assertEqual(self.first["verdicts"][rid], ("VALID", []), rid)
        self.assertEqual(self.first["verdicts"]["project"], "VALID")

    def test_two_runs_are_identical(self) -> None:
        self.assertEqual(sorted(self.first["artifacts"]), sorted(self.second["artifacts"]))
        for rel, text in self.first["artifacts"].items():
            self.assertEqual(text, self.second["artifacts"][rel], rel)


class SeriesEndToEnd(_SeriesEndToEnd, unittest.TestCase):
    CASE = CHAIN


class SeriesAllTypesEndToEnd(_SeriesEndToEnd, unittest.TestCase):
    """IMP-297: a spike, functional releases, an interleaved r2.1, a conditional and an integrator."""

    CASE = ALL_TYPES

    def test_one_source_gives_five_scope_items(self) -> None:
        index = self.first["artifacts"]["02_requirements/series/index.md"]
        self.assertIn("| r2.1 | `C-01` | `C-03` |", index)  # IMP-296: one source, five build items, local ids
        self.assertIn("| r4 | `C-01` | `C-05` |", index)

    def test_each_type_keeps_its_series_fields(self) -> None:
        briefs = {rid: self.first["artifacts"][f"02_requirements/{rid}/project-brief.md"] for rid in self.CASE.releases}
        self.assertIn("- `release_type`: measuring", briefs["r0"])
        self.assertIn("- `spike`: How long does the attachment scan take", briefs["r0"])
        self.assertIn("- `interleave_subtype`: change_found_in_testing", briefs["r2.1"])
        self.assertIn("- `condition`: `GAP-BRIEF-S5`", briefs["r3"])
        self.assertIn("- `integrator_consumption`: decision list ← K2 (r2); status column ← K3 (r2.1)", briefs["r4"])

    def test_the_guide_orders_the_interleaved_release_naturally(self) -> None:
        guide = self.first["artifacts"]["02_requirements/series/release-guide.md"]
        rows = [line.split("|")[1].strip().split()[0] for line in guide.splitlines() if line.startswith("| r")]
        self.assertEqual(rows[:6], ["r0", "r1", "r2", "r2.1", "r3", "r4"])


class SeriesRemainingTypesEndToEnd(_SeriesEndToEnd, unittest.TestCase):
    """IMP-298: an already built release, an enabler, a functional release and a segment cutover."""

    CASE = MORE_TYPES

    def _briefs(self) -> dict[str, str]:
        return {rid: self.first["artifacts"][f"02_requirements/{rid}/project-brief.md"] for rid in self.CASE.releases}

    def test_already_built_carries_its_validation_direction(self) -> None:
        briefs = self._briefs()
        self.assertIn("- `release_type`: already_built", briefs["r0"])
        self.assertIn("- `validation_direction`: built", briefs["r0"])
        self.assertIn("- Validation direction: built", briefs["r0"])
        for rid in ("r1", "r2", "r3"):  # only that release: the next ones go back to the normal direction
            self.assertIn("- Validation direction: to-build", briefs[rid], rid)
            self.assertNotIn("`validation_direction`", briefs[rid], rid)

    def test_the_enabler_says_what_it_supports_and_what_it_does_not_add(self) -> None:
        brief = self._briefs()["r1"]
        self.assertIn("- `release_type`: enabler", brief)
        self.assertIn("- `closing_check`: a policyholder and an adjuster sign in on the demo environment", brief)
        self.assertIn("- `supports`: online claim filing (r2) and the motor cutover (r3)", brief)
        self.assertIn("- `reduces_risk`: two releases inventing their own sign-in and roles", brief)
        self.assertIn("- `goes_first`: every claim screen needs the policyholder and adjuster roles", brief)
        self.assertIn("- `does_not_add`: claim screens: they live in r2; segment eligibility: it lives in r3", brief)

    def test_the_cutover_names_segment_eligibility_and_switch(self) -> None:
        brief = self._briefs()["r3"]
        self.assertIn("- `release_type`: segment_cutover", brief)
        self.assertIn("- `segment`: motor claims", brief)
        self.assertIn("- `eligibility`: a claim is eligible when its policy is a motor policy", brief)
        self.assertIn("- `switch`: online filing on for eligible claims; the others are generated in shadow", brief)

    def test_the_index_lists_every_remaining_type(self) -> None:
        index = self.first["artifacts"]["02_requirements/series/index.md"]
        for row in ("| r0 | Claim intake desk as it runs | already_built | 0 |", "| r1 | Policyholder and adjuster sign-in | enabler | 0 |",
                    "| r3 | Motor claims switched on | segment_cutover | 2 |"):
            self.assertIn(row, index)


if __name__ == "__main__":
    unittest.main()
