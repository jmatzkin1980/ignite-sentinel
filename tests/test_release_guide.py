"""IMP-269 (H17a′): closing a release, NOT READY by inheritance, the series guide.

Runs the synthetic series (tests/fixtures/synthetic_series, labelled) through the
v2 flow, confirms it, derives r1 and r2, and checks:
- the release brief is what a release derives from (it is never recompiled inside
  its mirror) and fresh derivations show no drift;
- r2 is NOT READY by inheritance while r1 is not closed;
- `/split --close` refuses until every story of r1 is Done and evidence exists,
  then records the close, unblocks r2 and keeps r3 waiting on r2;
- the guide and the readiness view's release axis.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.cli import main
from sentinel.memory import ContextBroker

ROOT = Path(__file__).resolve().parent
FX = ROOT / "fixtures" / "synthetic_series"
P = "CLAIMS"


class ReleaseGuideFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.old = os.getcwd()
        cls.tmp = tempfile.TemporaryDirectory()
        os.chdir(cls.tmp.name)
        cls.patch = patch.object(ContextBroker, "_connect_lancedb", lambda self: None)
        cls.patch.start()
        cls.base = Path("workspaces") / P
        cls.series = cls.base / "02_requirements" / "series"
        steps = [["init", P]] + [["ingest", P, "--source", str(FX / n)] for n in ("requirement.md", "approval_notes.md", "payment_notes.md")]
        steps += [["gaps", P], ["resolve-gaps", P, "--source", str(FX / "gap_responses.md")], ["maturity", P],
                  ["brief", P, "--profile", "UI", "--genesis", "greenfield"],
                  ["split", P, "--propose", "--source", str(FX / "proposal.json")],
                  ["split", P, "--confirm", "--ba", "Synthetic BA", "--tech", "Synthetic team"]]
        for rid in ("r1", "r2"):
            steps += [["specs", P, "--release", rid], ["backlog", P, "--release", rid], ["quality", P, "--release", rid]]
        for argv in steps:
            code, out = cls.cli(*argv)
            assert code == 0, (argv, out[-800:])
        cls.evidence = Path("closing-check-r1.md")
        cls.evidence.write_text("Synthetic closing check: a policyholder filed a claim end to end.\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.patch.stop()
        os.chdir(cls.old)
        cls.tmp.cleanup()

    @classmethod
    def cli(cls, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(list(argv))
        return code, out.getvalue()

    def verdict(self, rid: str) -> dict:
        code, out = self.cli("status", P, "--release", rid)
        self.assertEqual(code, 0, out)
        return json.loads(out[out.index("{"):])["verdict"]

    def close(self, rid: str, *extra: str) -> tuple[int, str]:
        return self.cli("split", P, "--close", rid, "--evidence", str(self.evidence), "--ba", "Synthetic BA",
                        "--tech", "Synthetic team", *extra)

    def finish_r1(self) -> None:
        stories = sorted(p.stem for p in (self.base / "04_backlog" / "r1").glob("US-*.md"))
        self.assertTrue(stories)
        for sid in stories:
            for status in ("Ready", "In Progress", "In Review", "Done"):
                self.assertEqual(self.cli("story-status", P, "--release", "r1", "--story", sid, "--set", status)[0], 0)

    def test_1_release_derives_from_its_own_brief(self) -> None:
        mirror = self.base / ".series_work" / "r1" / "workspaces" / P / "02_requirements" / "project-brief.md"
        self.assertEqual(mirror.read_bytes(), (self.base / "02_requirements" / "r1" / "project-brief.md").read_bytes())
        warnings = self.verdict("r1")["warnings"]
        self.assertFalse([w for w in warnings if "DRIFTED" in w], warnings)

    def test_2_inheritance_before_close(self) -> None:
        verdict = self.verdict("r2")
        self.assertEqual(verdict["verdict"], "NOT_READY")
        self.assertTrue(any("r2 depends hard on r1" in b for b in verdict["blockers"]))
        self.assertIn({"gate": "series_dependencies", "state": "WAITING", "blocks": True}, verdict["gate_matrix"])
        self.assertFalse(any("inheritance" in b for b in self.verdict("r1")["blockers"]))

    def test_3_close_refusals(self) -> None:
        code, out = self.close("r1")
        self.assertNotEqual(code, 0)
        self.assertIn("stories not Done", out)
        code, out = self.cli("split", P, "--close", "r1", "--ba", "A", "--tech", "T")
        self.assertIn("--evidence", out)
        code, out = self.cli("split", P, "--close", "r1", "--evidence", str(self.evidence), "--ba", "A")
        self.assertIn("--tech", out)
        code, out = self.close("r9")
        self.assertIn("not a release", out)
        partition = json.loads((self.series / "partition.json").read_text(encoding="utf-8"))
        self.assertNotIn("closed", partition)

    def test_4_close_unblocks_and_the_guide_shows_it(self) -> None:
        self.finish_r1()
        code, out = self.close("r1")
        self.assertEqual(code, 0, out)
        result = json.loads(out)
        self.assertEqual(result["unblocked"], ["r2"])
        partition = json.loads((self.series / "partition.json").read_text(encoding="utf-8"))
        self.assertEqual(len(partition["closed"]["r1"]["evidence_sha256"]), 64)
        self.assertFalse(any("inheritance" in b for b in self.verdict("r2")["blockers"]))
        guide = (self.series / "release-guide.md").read_text(encoding="utf-8")
        self.assertIn("closed ", guide)
        self.assertIn("NOT READY by inheritance: depends hard on r2, not closed", guide)
        self.assertIn("## Coverage matrix", guide)
        self.assertNotEqual(self.close("r1")[0], 0)  # already closed
        self.assertEqual(self.cli("split", P, "--confirm", "--ba", "Synthetic BA", "--tech", "Synthetic team")[0], 0)
        partition = json.loads((self.series / "partition.json").read_text(encoding="utf-8"))
        self.assertIn("r1", partition["closed"])  # survives a confirmation

    def test_5_views(self) -> None:
        code, out = self.cli("view", P, "--artifact", "release-guide")
        self.assertEqual(code, 0, out)
        code, out = self.cli("view", P, "--artifact", "readiness")
        self.assertEqual(code, 0, out)
        from sentinel.readiness_view import collect_readiness_model

        items = {i["id"]: i for i in collect_readiness_model(P)["items"] if i["kind"] == "release"}
        self.assertEqual(sorted(items), ["r1", "r2", "r3"])
        self.assertEqual(items["r3"]["verdict"], "NOT_READY")

    def test_6_mcp_mode(self) -> None:
        from sentinel.mcp import SPLIT_MODES

        self.assertIn("close", SPLIT_MODES)


if __name__ == "__main__":
    unittest.main()
