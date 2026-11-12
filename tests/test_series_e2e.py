"""IMP-26v (H17a close): the release series end to end, on a synthetic multi-release fixture.

`tests/fixtures/synthetic_series/` is labelled synthetic: three sources (filing,
approval, payment), the gap answers, and the agent's proposal. The flow:

v2 flow → `/split --assess` → `--propose` → validation → `--confirm` (index and
release briefs) → per release `specs`, `backlog` (with the slice plan), `quality`
and `/validate` VALID. Two full runs give identical release artifacts. The
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
from pathlib import Path
from unittest.mock import patch

from sentinel.cli import main
from sentinel.memory import ContextBroker

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from golden_normalize import normalize  # noqa: E402

FX = ROOT / "fixtures" / "synthetic_series"
P = "CLAIMS"
RELEASES = ("r1", "r2", "r3")
COMPARED = ("02_requirements/series", "02_requirements/r1", "02_requirements/r2", "02_requirements/r3",
            *(f"{folder}/{rid}" for folder in ("03_specs", "04_backlog", "05_quality") for rid in RELEASES))


def _cli(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(argv)
    return code, out.getvalue()


def run_series(work: Path) -> dict:
    """The whole flow in `work`; returns exit codes, validate verdicts and the normalized artifacts."""
    old = os.getcwd()
    os.chdir(work)
    result: dict = {"codes": {}, "verdicts": {}, "artifacts": {}}
    try:
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            steps = [["init", P]]
            steps += [["ingest", P, "--source", str(FX / name)] for name in ("requirement.md", "approval_notes.md", "payment_notes.md")]
            steps += [["gaps", P], ["resolve-gaps", P, "--source", str(FX / "gap_responses.md")], ["maturity", P],
                      ["brief", P, "--profile", "UI", "--genesis", "greenfield"], ["split", P, "--assess"],
                      ["split", P, "--propose", "--source", str(FX / "proposal.json")],
                      ["split", P, "--confirm", "--ba", "Synthetic BA", "--tech", "Synthetic team"]]
            for rid in RELEASES:
                steps += [["specs", P, "--release", rid], ["backlog", P, "--release", rid], ["quality", P, "--release", rid]]
            for argv in steps:
                code, text = _cli(argv)
                result["codes"][" ".join(a for a in argv if not a.startswith(str(FX)))] = code
                if code:
                    result.setdefault("errors", []).append(text[-600:])
            for rid in RELEASES:
                _, text = _cli(["validate", P, "--release", rid])
                verdict = json.loads(text[text.index("{"):])
                result["verdicts"][rid] = (verdict["verdict"], verdict["findings"])
            _, text = _cli(["validate", P])
            result["verdicts"]["project"] = json.loads(text[text.index("{"):])["verdict"]
        base = work / "workspaces" / P
        roots = {str(work.resolve()), work.resolve().as_posix(), str(work.resolve()).replace("\\", "\\\\")}
        for rel in COMPARED:
            for path in sorted((base / rel).rglob("*")):
                if path.is_file() and path.suffix in {".md", ".json"}:
                    text = path.read_text(encoding="utf-8")
                    for root in sorted(roots, key=len, reverse=True):
                        text = text.replace(root, "[ROOT]")
                    result["artifacts"][path.relative_to(base).as_posix()] = normalize(text, P)
    finally:
        os.chdir(old)
    return result


class SeriesEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = [tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory()]
        cls.first = run_series(Path(cls.tmp[0].name))
        cls.second = run_series(Path(cls.tmp[1].name))

    @classmethod
    def tearDownClass(cls) -> None:
        for tmp in cls.tmp:
            tmp.cleanup()

    def test_fixture_is_labelled_synthetic(self) -> None:
        for path in FX.iterdir():
            self.assertIn("synthetic", path.read_text(encoding="utf-8").lower(), path.name)

    def test_every_step_succeeds(self) -> None:
        self.assertEqual([k for k, v in self.first["codes"].items() if v], [], self.first.get("errors"))

    def test_series_is_compiled(self) -> None:
        artifacts = self.first["artifacts"]
        self.assertIn("02_requirements/series/index.md", artifacts)
        for rid in RELEASES:
            self.assertIn(f"02_requirements/{rid}/project-brief.md", artifacts)
            for rel in (f"03_specs/{rid}/prd.md", f"03_specs/{rid}/specs.md", f"04_backlog/{rid}/SLICE-PLAN.md",
                        f"05_quality/{rid}/backlog_readiness_audit.md"):
                self.assertIn(rel, artifacts)

    def test_each_release_validates(self) -> None:
        for rid in RELEASES:
            self.assertEqual(self.first["verdicts"][rid], ("VALID", []), rid)
        self.assertEqual(self.first["verdicts"]["project"], "VALID")

    def test_two_runs_are_identical(self) -> None:
        self.assertEqual(sorted(self.first["artifacts"]), sorted(self.second["artifacts"]))
        for rel, text in self.first["artifacts"].items():
            self.assertEqual(text, self.second["artifacts"][rel], rel)


if __name__ == "__main__":
    unittest.main()
