"""IMP-248 — one counts-based "ready to build" verdict, the same on every surface.

`build_readiness_verdict(project_id, release=None)` is the single source of the
verdict, the gap counts and the next step for `/status`, `/dashboard` and MCP.
Rules (doc 51 / doc 49 §5):
- counts come from one counter over gaps.md that honors the configured blocking
  severities (it used to be two counters with "critical/high" hardcoded);
- never READY with a blocking gap open;
- DEFERRED_TO_CONTEXT units are reported but do not block;
- a "test before advancing" assumption is a warning;
- a check that could not run is attached to the verdict and never shows green;
- the maturity score stays published next to the verdict.
`/status` prints the summary by default and the full dump with `--full`.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sentinel import readiness_verdict as rv
from sentinel.cli import main
from sentinel.dashboard import collect_dashboard_model
from sentinel.discovery import parse_gap_rows
from sentinel.readiness_verdict import build_readiness_verdict, count_gaps
from sentinel.status import project_status

REPO = Path(__file__).resolve().parents[1]
RAW = (
    "# Reporting Portal\n\n"
    "We need a reporting portal for the operations team. The objective is to "
    "reduce manual work. Data is stored in the legacy billing system.\n"
)
GATES = {"gaps", "brief_gate", "implementability_gate", "crystallization_gate", "drift", "story_dor", "sources"}


def _cli_json(argv: list[str]) -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(argv)
    assert code == 0, out.getvalue()
    return json.loads(out.getvalue())


class CounterTests(unittest.TestCase):
    ROWS = [
        {"id": "GAP-A", "severity": "high", "status": "OPEN"},
        {"id": "GAP-B", "severity": "medium", "status": "OPEN"},
        {"id": "GAP-C", "severity": "critical", "status": "ANSWERED"},
        {"id": "GAP-D", "severity": "low", "status": "PARTIALLY_CLOSED"},
        {"id": "GAP-E", "severity": "high", "status": "CLOSED"},
    ]

    def test_one_counter_with_every_state(self) -> None:
        self.assertEqual(count_gaps(self.ROWS), {
            "open": 2, "answered": 1, "partially_closed": 1, "closed": 1, "blocking_open": 2, "total": 5,
        })

    def test_blocking_follows_the_configured_severities(self) -> None:
        self.assertEqual(count_gaps(self.ROWS, {"critical"})["blocking_open"], 1)
        self.assertEqual(count_gaps(self.ROWS, {"critical", "high", "medium"})["blocking_open"], 3)


class VerdictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "VRD", "--brief-version", "1"]), 0)
        self.ws = self.temp / "workspaces" / "VRD"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _ingest(self) -> None:
        src = self.temp / "raw.md"
        src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["ingest", "VRD", "--source", str(src)]), 0)

    def _gaps(self) -> list[dict]:
        return parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))

    def _close(self, gap_ids: list[str]) -> None:
        response = self.temp / "close.md"
        response.write_text("".join(
            f"### {gap_id}\n\n- Answer: Confirmed by the operations lead.\n- Owner / source: Ops lead\n"
            "- Evidence or reference: kickoff notes\n- Decision status: confirmed\n\n"
            for gap_id in gap_ids
        ), encoding="utf-8")
        self.assertEqual(main(["resolve-gaps", "VRD", "--source", str(response)]), 0)

    def _blocking_ids(self) -> list[str]:
        return sorted(g["id"].strip("`") for g in self._gaps() if g["severity"].lower() in {"critical", "high"})

    def test_without_discovery_it_is_not_ready_and_says_ingest(self) -> None:
        verdict = build_readiness_verdict("VRD")
        self.assertEqual(verdict["verdict"], "NOT_READY")
        self.assertEqual(verdict["next_step"]["key"], "ingest")

    def test_a_blocking_gap_means_not_ready(self) -> None:
        self._ingest()
        verdict = build_readiness_verdict("VRD")
        self.assertEqual(verdict["verdict"], "NOT_READY")
        self.assertEqual(sorted(verdict["blocking_open"]), self._blocking_ids())
        self.assertEqual(verdict["counts"]["blocking_open"], len(verdict["blocking_open"]))
        self.assertEqual(verdict["next_step"]["key"], "resolve_blocking")

    def test_counts_honor_the_configured_blocking_severities(self) -> None:
        self._ingest()
        config = self.ws / "sentinel.config.yaml"
        config.write_text(config.read_text(encoding="utf-8").replace("    - critical\n    - high\n", "    - critical\n"), encoding="utf-8")
        critical = [g for g in self._gaps() if g["severity"].lower() == "critical"]
        self.assertEqual(build_readiness_verdict("VRD")["counts"]["blocking_open"], len(critical))

    def test_an_unrun_check_never_shows_green(self) -> None:
        self._ingest()
        self._close(self._blocking_ids())
        verdict = build_readiness_verdict("VRD")
        self.assertEqual(verdict["blocking_open"], [])
        self.assertNotEqual(verdict["verdict"], "READY")
        self.assertIn("story_dor", [item["check"] for item in verdict["partial_coverage"]])

    def test_deferred_to_context_warns_but_does_not_block(self) -> None:
        self._ingest()
        self._close(self._blocking_ids())
        gate = {"state": "READY_PENDING_DOMAIN_CONTEXT", "not_implementable_units": [], "deferred_units": ["RU-001"], "blocks_by_default": False}
        fake = {"summary": {"units_total": 1, "implementable": [], "deferred_to_context": ["RU-001"], "not_implementable": [], "gate": gate}}
        with mock.patch.object(rv, "compute_unit_implementability", return_value=fake):
            verdict = build_readiness_verdict("VRD")
        self.assertNotEqual(verdict["verdict"], "NOT_READY")
        self.assertTrue(any("RU-001" in w and "DEFERRED_TO_CONTEXT" in w for w in verdict["warnings"]), verdict["warnings"])

    def test_test_before_advancing_assumption_is_a_warning(self) -> None:
        self._ingest()
        self._close(self._blocking_ids())
        projection = {"summary": {"test_before_advancing_ids": ["ASM-RISKY"]}}
        with mock.patch.object(rv, "assumptions_projection", return_value=projection):
            verdict = build_readiness_verdict("VRD")
        self.assertNotEqual(verdict["verdict"], "NOT_READY")
        self.assertTrue(any("ASM-RISKY" in w for w in verdict["warnings"]))

    def test_release_is_accepted_and_reported_as_not_scoped_yet(self) -> None:
        self._ingest()
        verdict = build_readiness_verdict("VRD", release="r1")
        self.assertEqual(verdict["release"], "r1")
        self.assertIn("release", [item["check"] for item in verdict["partial_coverage"]])

    def test_score_and_gate_matrix_are_published(self) -> None:
        self._ingest()
        verdict = build_readiness_verdict("VRD")
        self.assertIsInstance(verdict["maturity_score"], float)
        self.assertEqual({row["gate"] for row in verdict["gate_matrix"]}, GATES)
        gaps_gate = next(row for row in verdict["gate_matrix"] if row["gate"] == "gaps")
        self.assertTrue(gaps_gate["blocks"])

    def test_same_verdict_on_every_surface(self) -> None:
        self._ingest()
        expected = build_readiness_verdict("VRD")
        cli = _cli_json(["status", "VRD"])
        self.assertEqual(cli["verdict"], expected)
        self.assertEqual(project_status("VRD")["verdict"], expected)
        workspace = next(w for w in collect_dashboard_model(self.temp)["workspaces"] if w["project_id"] == "VRD")
        self.assertEqual(workspace["verdict"]["verdict"], expected["verdict"])
        self.assertEqual(workspace["next_action"]["key"], expected["next_step"]["key"])
        self.assertEqual({k: cli["gap_counts"][k] for k in expected["counts"]}, expected["counts"])

    def test_status_is_a_summary_by_default(self) -> None:
        self._ingest()
        summary = _cli_json(["status", "VRD"])
        full = _cli_json(["status", "VRD", "--full"])
        self.assertNotIn("maturity_metrics", summary)
        self.assertIn("maturity_metrics", full)
        self.assertLess(len(json.dumps(summary)), len(json.dumps(full)) / 3)
        # development_readiness used to appear twice in the full dump.
        self.assertNotIn("development_readiness", full["maturity_metrics"])
        self.assertIn("development_readiness", full)
        for key in ("verdict", "gap_counts", "next_step", "readiness_stage", "maturity_score"):
            self.assertIn(key, summary)


class SingleSourceGuards(unittest.TestCase):
    def test_no_duplicate_counter_or_next_step(self) -> None:
        sources = {p.relative_to(REPO).as_posix(): p.read_text(encoding="utf-8") for p in (REPO / "sentinel").rglob("*.py")}
        self.assertFalse([k for k, t in sources.items() if "def count_gap_rows" in t or "def recommend_next_step" in t])

    def test_no_hardcoded_blocking_severities_in_counters(self) -> None:
        offenders = []
        for path in (REPO / "sentinel").rglob("*.py"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"severity in \{\"critical\", \"high\"\}", line):
                    offenders.append(f"{path.relative_to(REPO).as_posix()}:{number}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
