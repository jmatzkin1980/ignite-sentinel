"""IMP-267a (H17a): compiling the series, the index and one brief per release.

The whole brief v2 stays the source; the confirmed partition routes each unit to its
release. Other releases' units become tombstones, the build items become local ids
mapped in the index, a moved unit is REATRIBUIDO, and recompiling is the sync.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.release_series import assign_owners, compile_release_brief, refresh_series_if_stale, render_index

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "evals" / "partition" / "valid-partition.json"
VALID = json.loads(FIXTURE.read_text(encoding="utf-8"))


def release(payload: dict, rid: str) -> dict:
    return next(r for r in payload["releases"] if r["id"] == rid)


class PureTests(unittest.TestCase):
    def test_tombstones_local_ids_and_series_block(self) -> None:
        assignment = assign_owners(VALID["brief"], VALID["payload"])
        text, local = compile_release_brief(VALID["brief"], VALID["payload"], "r2", assignment, "en")
        self.assertEqual(local, {"C-02": "C-01"})
        self.assertIn("- `C-01` Claim approval", text)
        self.assertIn("➡ lives in r1: `C-01` Claim filing", text)
        self.assertIn("➡ lives in r3: Payment of approved claims.", text)
        self.assertIn("➡ outside the horizon: status tracking", text)
        self.assertIn("- Claim approval by adjusters.", text)
        self.assertIn("- `release_type`: functional", text)
        self.assertIn("- `depends_on`: r0 (hard, K1: it applies the authorization filter); r1 (hard, K2:", text)
        self.assertIn("· r2 Adjuster approval", text.splitlines()[1])
        self.assertIn("Every module uses a shared authorization filter.", text)  # shared lines stay

    def test_tombstone_of_a_build_item_points_to_the_local_id_there(self) -> None:
        assignment = assign_owners(VALID["brief"], VALID["payload"])
        text, _ = compile_release_brief(VALID["brief"], VALID["payload"], "r1", assignment, "en")
        self.assertIn("➡ lives in r3: `C-03` Claim payment — depends on: none → r3 `C-01`", text)

    def test_spanish_copy(self) -> None:
        assignment = assign_owners(VALID["brief"], VALID["payload"])
        text, _ = compile_release_brief(VALID["brief"], VALID["payload"], "r1", assignment, "es")
        self.assertIn("➡ vive en r2:", text)
        self.assertIn("#### Release en la serie", text)

    def test_index_sorts_in_natural_order(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        for rid in ("r10", "r2.1"):
            payload["releases"].append({"id": rid, "name": rid, "type": "functional", "wave": 4, "goal": "g"})
        index = render_index("P", payload, {"confirmed_by": {"ba": "Ana", "technical_team": "Core"}}, "abc",
                             {}, [], {"unresolved": [], "unrouted": [], "integrity": {}}, "en")
        rows = [line.split("|")[1].strip() for line in index.splitlines() if line.startswith("| r")]
        self.assertEqual(rows, ["r0", "r1", "r2", "r2.1", "r3", "r10"])


class SeriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "P"]), 0)
        self.base = Path("workspaces") / "P"
        self.brief = self.base / "02_requirements" / "project-brief.md"
        self.brief.parent.mkdir(parents=True, exist_ok=True)
        self.brief.write_text(VALID["brief"], encoding="utf-8")
        from sentinel.discovery import render_gaps

        rows = [{"id": g, "lens": "business", "severity": "high", "status": "OPEN", "description": "synthetic gap",
                 "question": "Which?", "evidence_mention": "§6.1", "origin": "agent", "resolution_note": ""}
                for g in VALID["open_gaps"]]
        gaps = self.base / "01_discovery" / "gaps.md"
        gaps.parent.mkdir(parents=True, exist_ok=True)
        gaps.write_text(render_gaps("P", rows, "REQ-001", "en"), encoding="utf-8")
        manifest = self.base / "00_raw" / "source_manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"registry": [{"id": "F-01", "paths": ["00_raw/syn.md"], "validity": "current"}]}),
                            encoding="utf-8")
        self.series = self.base / "02_requirements" / "series"

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def confirm(self, payload: dict) -> str:
        Path("proposal.json").write_text(json.dumps(payload), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            self.assertEqual(main(["split", "P", "--propose", "--source", "proposal.json"]), 0, out.getvalue())
            self.assertEqual(main(["split", "P", "--confirm", "--ba", "Ana", "--tech", "Core"]), 0, out.getvalue())
        return out.getvalue()

    def read(self, rel: str) -> str:
        return (self.base / rel).read_text(encoding="utf-8")

    def test_no_partition_no_series(self) -> None:
        self.assertIsNone(refresh_series_if_stale("P"))
        self.assertFalse(self.series.exists())

    def test_confirm_compiles_the_index_and_every_release(self) -> None:
        self.confirm(VALID["payload"])
        for rid in ("r0", "r1", "r2", "r3"):
            self.assertTrue((self.base / "02_requirements" / rid / "project-brief.md").is_file(), rid)
        index = self.read("02_requirements/series/index.md")
        self.assertIn("| r2 | `C-01` | `C-02` |", index)
        self.assertIn("The SAD and the prototype are not split", index)
        self.assertIn("No findings", index)  # integrity and anchors pass on every release
        report = json.loads(self.read("02_requirements/series/series_report.json"))
        self.assertEqual((report["status"], report["integrity"], report["unrouted"]), ("compiled", {}, []))

    def test_recompiling_the_same_brief_is_identical(self) -> None:
        self.confirm(VALID["payload"])
        before = {p: p.read_bytes() for p in sorted(self.base.joinpath("02_requirements").rglob("*.md"))}
        (self.series / "series_map.json").unlink()  # force a recompile
        self.assertEqual(refresh_series_if_stale("P")["status"], "compiled")
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_a_brief_change_recompiles_and_flags_unrouted_units(self) -> None:
        self.confirm(VALID["payload"])
        text = VALID["brief"].replace("- Payment of approved claims.",
                                      "- Claim reopening by policyholders. [[sources § Source log - SYN # F-01 — supports: x]]\n- Payment of approved claims.")
        self.brief.write_text(text, encoding="utf-8")
        result = refresh_series_if_stale("P")
        self.assertEqual(result["status"], "compiled")
        self.assertIn("➡ not routed to any release: propose the series again: Claim reopening by policyholders.",
                      self.read("02_requirements/r1/project-brief.md"))
        index = self.read("02_requirements/series/index.md")
        self.assertIn("Claim reopening by policyholders. is not routed", index)
        self.assertIn("The brief changed since the confirmation", index)
        self.assertIsNone(refresh_series_if_stale("P"))  # in sync now

    def test_a_moved_unit_is_reattributed(self) -> None:
        self.confirm(VALID["payload"])
        payload = copy.deepcopy(VALID["payload"])
        unit = {"place": "2.1", "quote": "Back office adjusters review and approve claims"}
        release(payload, "r2")["contains"].remove(unit)
        release(payload, "r1")["contains"].append(unit)
        self.confirm(payload)
        self.assertIn("➡ REATRIBUIDO (reattributed) to r1: Back office adjusters review and approve claims.",
                      self.read("02_requirements/r2/project-brief.md"))
        self.assertIn("Back office adjusters review and approve claims.: r2 → r1", self.read("02_requirements/series/index.md"))

    def test_a_v1_brief_blocks_the_series(self) -> None:
        self.confirm(VALID["payload"])
        self.brief.write_text("# Project Brief\n\n## 1. Identidad\n\n- x\n", encoding="utf-8")
        result = refresh_series_if_stale("P")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("A43", result["reason"])
        self.assertEqual(json.loads(self.read("02_requirements/series/series_report.json"))["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
