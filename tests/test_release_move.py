"""IMP-268 (H17a′): re-scope and cascade, `/split --move`.

A unit moves between releases (or to a sketch) as a governed change of the
partition: green validation, a new confirmation, a recompiled series with
REATRIBUIDO tombstones, and a dated record. A round trip is refused until it names
the written criterion that decides it; excluded is not resolved.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sentinel.cli import main
from sentinel.release_move import CRITERION_GAP_ID, ReleaseSplitError, plan_move

ROOT = Path(__file__).resolve().parent
VALID = json.loads((ROOT / "fixtures" / "evals" / "partition" / "valid-partition.json").read_text(encoding="utf-8"))
SKETCH = "sketch:status tracking"


class PlanTests(unittest.TestCase):
    def test_moves_one_unit(self) -> None:
        moved, unit = plan_move(VALID["payload"], "C-04", SKETCH, "r1")
        self.assertEqual(unit, {"item": "C-04"})
        r1 = next(r for r in moved["releases"] if r["id"] == "r1")
        self.assertIn({"item": "C-04"}, r1["contains"])
        self.assertEqual(moved["sketches"][0]["contains"], [])
        self.assertIn({"item": "C-04"}, VALID["payload"]["sketches"][0]["contains"])  # the input is untouched

    def test_refusals(self) -> None:
        for spec, src, dst, message in (("claim", "r1", "r2", "matches 2 units"), ("C-99", "r1", "r2", "is not a unit of r1"),
                                        ("C-01", "r1", "r1", "same holder"), ("C-01", "r9", "r2", "--from"),
                                        ("C-01", "r1", "sketch:nope", "--to")):
            with self.subTest(spec=spec, src=src, dst=dst), self.assertRaises(ReleaseSplitError) as caught:
                plan_move(VALID["payload"], spec, src, dst)
            self.assertIn(message, str(caught.exception))


class MoveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "P"]), 0)
        self.base = Path("workspaces") / "P"
        brief = self.base / "02_requirements" / "project-brief.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text(VALID["brief"], encoding="utf-8")
        from sentinel.discovery import render_gaps

        rows = [{"id": g, "lens": "business", "severity": "high", "status": "OPEN", "description": "synthetic gap",
                 "question": "Which?", "evidence_mention": "§6.1", "origin": "agent", "resolution_note": ""}
                for g in VALID["open_gaps"]]
        self.gaps = self.base / "01_discovery" / "gaps.md"
        self.gaps.parent.mkdir(parents=True, exist_ok=True)
        self.gaps.write_text(render_gaps("P", rows, "REQ-001", "en"), encoding="utf-8")
        self.series = self.base / "02_requirements" / "series"
        Path("proposal.json").write_text(json.dumps(VALID["payload"]), encoding="utf-8")
        self.assertEqual(self.cli("--propose", "--source", "proposal.json")[0], 0)
        self.assertEqual(self.cli("--confirm", "--ba", "Ana", "--tech", "Core")[0], 0)

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def cli(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(["split", "P", *args])
        return code, out.getvalue()

    def move(self, unit: str, src: str, dst: str, *extra: str) -> tuple[int, str]:
        return self.cli("--move", "--unit", unit, "--from", src, "--to", dst, "--reason", "the client asked for it",
                        "--ba", "Bea", "--tech", "Platform", *extra)

    def changes(self) -> list[dict]:
        path = self.series / "scope_changes.json"
        return json.loads(path.read_text(encoding="utf-8"))["changes"] if path.exists() else []

    def gap_status(self, gap: str) -> str | None:
        from sentinel.discovery import parse_gap_rows

        rows = parse_gap_rows(self.gaps.read_text(encoding="utf-8"))
        return next((r.get("status") for r in rows if r.get("id", "").strip("`") == gap), None)

    def test_move_recompiles_records_and_confirms_again(self) -> None:
        code, out = self.move("C-04", SKETCH, "r1", "--finding", "F-01")
        self.assertEqual(code, 0, out)
        result = json.loads(out)
        self.assertEqual(result["status"], "moved")
        self.assertIn("r1", result["releases_changed"])
        change = self.changes()[0]
        self.assertRegex(change["date"], r"^\d{4}-\d\d-\d\d$")
        self.assertEqual((change["unit"], change["from"], change["to"], change["finding"]), ("C-04", SKETCH, "r1", "F-01"))
        self.assertIn("| C-04 | sketch:status tracking | r1 |", (self.series / "scope_changes.md").read_text(encoding="utf-8"))
        partition = json.loads((self.series / "partition.json").read_text(encoding="utf-8"))
        self.assertEqual(partition["confirmed_by"], {"ba": "Bea", "technical_team": "Platform"})
        r1 = (self.base / "02_requirements" / "r1" / "project-brief.md").read_text(encoding="utf-8")
        self.assertIn("`C-02` Claim status tracking", r1)  # local id in r1
        r2 = (self.base / "02_requirements" / "r2" / "project-brief.md").read_text(encoding="utf-8")
        self.assertIn("REATRIBUIDO (reattributed) to r1: `C-04` Claim status tracking", r2)

    def test_round_trip_is_refused_until_a_criterion_decides_it(self) -> None:
        self.assertEqual(self.move("C-04", SKETCH, "r1")[0], 0)
        before = (self.series / "proposal.json").read_bytes()
        code, out = self.move("C-04", "r1", SKETCH)
        self.assertNotEqual(code, 0)
        self.assertIn("round trip", out)
        self.assertEqual(self.gap_status(CRITERION_GAP_ID), "OPEN")
        self.assertEqual((self.series / "proposal.json").read_bytes(), before)
        self.assertEqual(len(self.changes()), 1)
        self.assertNotEqual(self.move("C-04", "r1", SKETCH, "--criterion", "C9")[0], 0)  # not written
        code, out = self.move("C-04", "r1", SKETCH, "--criterion", "C1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.changes()[-1]["criterion"], "C1")

    def test_excluded_is_not_resolved(self) -> None:
        code, out = self.move("Payment of approved claims", "r3", SKETCH)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.gap_status("GAP-BRIEF-S5"), "OPEN")

    def test_a_red_partition_changes_nothing(self) -> None:
        before = {p.name: p.read_bytes() for p in self.series.iterdir() if p.is_file()}
        red = {"findings": [{"code": "asymmetric_edge", "where": "r1 → r0", "reason": "seeded"}]}
        with mock.patch("sentinel.release_move.validate_partition", return_value=red):
            code, out = self.move("C-04", SKETCH, "r1")
        self.assertNotEqual(code, 0)
        self.assertIn("asymmetric_edge", out)
        self.assertEqual({p.name: p.read_bytes() for p in self.series.iterdir() if p.is_file()}, before)

    def test_reason_and_confirmers_are_required(self) -> None:
        code, out = self.cli("--move", "--unit", "C-04", "--from", SKETCH, "--to", "r1", "--ba", "Bea", "--tech", "Platform")
        self.assertNotEqual(code, 0)
        self.assertIn("--reason", out)
        code, out = self.cli("--move", "--unit", "C-04", "--from", SKETCH, "--to", "r1", "--reason", "x", "--ba", "Bea")
        self.assertNotEqual(code, 0)
        self.assertIn("--tech", out)
        self.assertEqual(self.changes(), [])

    def test_mcp_modes(self) -> None:
        from sentinel.mcp import SPLIT_MODES

        self.assertIn("move", SPLIT_MODES)
        self.assertTrue(re.search(r"mode=move", __import__("sentinel.mcp", fromlist=["TOOL_DESCRIPTIONS"]).TOOL_DESCRIPTIONS["split"]))


if __name__ == "__main__":
    unittest.main()
