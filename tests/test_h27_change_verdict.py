"""IMP-406 (H27 inc 1) task 6: the change readiness verdict (the project's rule) and the class of deferred questions."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_cli, run_ok  # noqa: E402
from test_h26_cross_record import CID, PID, CrossCase, set_language  # noqa: E402

from sentinel import mcp as sentinel_mcp  # noqa: E402
from sentinel.changes import deferred_gaps, list_changes, set_gap_impact  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import close_change_gap, record_cross, retire_change_gaps  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.readiness_verdict import build_change_verdict, decide_verdict  # noqa: E402
from sentinel.workspace import read_state, update_state  # noqa: E402
from test_mcp_parity import _tools  # noqa: E402

COMPLETE = {"state": "current", "total": 10, "covered": 10, "pending": 0, "proposed": 0, "flagged": 0, "complete": True,
            "text": "10 de 10", "orphans": [], "unreadable": []}


class Rule(unittest.TestCase):
    def test_decide_verdict_is_shared(self):
        self.assertEqual(decide_verdict(["x"], []), "NOT_READY")
        self.assertEqual(decide_verdict([], ["y"]), "READY_WITH_WARNINGS")
        self.assertEqual(decide_verdict([], []), "READY")
        self.assertEqual(decide_verdict([], [], [{"check": "c"}]), "READY_WITH_WARNINGS")


class Verdict(CrossCase):
    def setUp(self):
        super().setUp()
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        forget_read_snapshots()
        # the lens round also left medium questions open: close them so only the cross-read's two stay deferred
        crossed = ("GAP-DIS-", "GAP-SRD-", "GAP-SED-")
        retire_change_gaps(PID, CID, [i for i in self.gaps() if not i.startswith(crossed)], "cerrada para la prueba")
        forget_read_snapshots()

    def gap(self, prefix: str) -> str:
        return next(i for i in self.gaps() if i.startswith(prefix))

    def settled(self):
        """Extraction complete, no cross missing and no blocking question counted: only the deferred ones speak."""
        changes = {k: dict(v) for k, v in list_changes(PID).items()}
        changes[CID]["gap_counts"] = {**changes[CID]["gap_counts"], "blocking_open": 0}
        update_state(PID, changes=changes)
        return (
            patch("sentinel.extraction.coverage.extraction_coverage", return_value=COMPLETE),
            patch("sentinel.extraction.coverage.preserved_coverage", return_value={"surfaces": [], "rows": {}, "missing": [], "complete": True}),
            patch("sentinel.crosses.state.cross_status", return_value={"missing": []}),
            patch("sentinel.change_escalation.escalation_warnings", return_value=[]),
        )

    def verdict(self, patches) -> dict:
        from contextlib import ExitStack

        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            return build_change_verdict(PID, CID)

    def test_blocking_is_not_ready(self):
        verdict = build_change_verdict(PID, CID)
        self.assertEqual(verdict["verdict"], "NOT_READY")
        self.assertIn("1 pregunta(s) bloqueante(s) abierta(s)", verdict["blockers"])
        gate = next(g for g in verdict["gate_matrix"] if g["gate"] == "gaps")
        self.assertEqual(gate, {"gate": "gaps", "state": "OPEN", "blocks": True})
        self.assertEqual(verdict["deferred"], {"construccion": 2, "operativo": 0})
        self.assertEqual([g["gate"] for g in verdict["gate_matrix"]], ["gaps", "extraction", "crosses", "deferred", "verification"])

    def test_deferred_default_to_construction(self):
        verdict = self.verdict(self.settled())
        srd, sed = self.gap("GAP-SRD-"), self.gap("GAP-SED-")
        listed = ", ".join(d["id"] for d in deferred_gaps(PID, CID))
        self.assertEqual(verdict["verdict"], "NOT_READY")
        self.assertEqual(verdict["blockers"], [f"2 pendiente(s) diferido(s) frenan la construcción: {listed}"])
        self.assertIn(srd, listed)
        self.assertIn(sed, listed)
        gate = next(g for g in verdict["gate_matrix"] if g["gate"] == "deferred")
        self.assertEqual(gate, {"gate": "deferred", "state": "BUILD", "blocks": True})

    def test_operational_gives_warnings(self):
        for prefix in ("GAP-SRD-", "GAP-SED-"):
            run_ok(["gaps", PID, "--change", CID, "--id", self.gap(prefix), "--impact", "operativo",
                    "--reason", "lo define el área de Compras"])
        forget_read_snapshots()
        verdict = self.verdict(self.settled())
        listed = ", ".join(d["id"] for d in deferred_gaps(PID, CID))
        self.assertEqual(verdict["verdict"], "READY_WITH_WARNINGS")
        self.assertEqual(verdict["blockers"], [])
        self.assertEqual(verdict["warnings"], [f"2 pendiente(s) diferido(s) operativo(s): {listed}"])
        self.assertEqual(verdict["deferred"], {"construccion": 0, "operativo": 2})
        marks = read_state(PID)["changes"][CID]["gap_impact"]
        self.assertEqual(marks[self.gap("GAP-SED-")]["reason"], "lo define el área de Compras")
        self.assertEqual(marks[self.gap("GAP-SED-")]["impact"], "operativo")
        self.assertIn("at", marks[self.gap("GAP-SED-")])
        # the class survives the next rewrite of the change's gaps
        run_ok(["gaps", PID, "--change", CID])
        self.assertEqual(read_state(PID)["changes"][CID]["gap_impact"], marks)

    def test_ready(self):
        for prefix in ("GAP-SRD-", "GAP-SED-"):
            self.assertTrue(close_change_gap(PID, CID, self.gap(prefix), "resuelta"))
        forget_read_snapshots()
        verdict = self.verdict(self.settled())
        self.assertEqual(verdict["verdict"], "READY")
        self.assertEqual(verdict["blockers"], [])
        self.assertEqual(verdict["warnings"], [])
        self.assertEqual(verdict["deferred"], {"construccion": 0, "operativo": 0})

    def test_impact_errors(self):
        dis = self.gap("GAP-DIS-")
        with self.assertRaises(InputError) as blocking:
            set_gap_impact(PID, CID, dis, "operativo", "r")
        self.assertIn("es bloqueante", str(blocking.exception))
        with self.assertRaises(InputError) as unknown:
            set_gap_impact(PID, CID, "GAP-ZZZ", "operativo", "r")
        self.assertIn("no es una pregunta de CHG-001", str(unknown.exception))
        sed = self.gap("GAP-SED-")
        close_change_gap(PID, CID, sed, "resuelta")
        forget_read_snapshots()
        with self.assertRaises(InputError) as closed:
            set_gap_impact(PID, CID, sed, "operativo", "r")
        self.assertIn("ya está cerrada", str(closed.exception))
        with self.assertRaises(InputError) as reasonless:
            set_gap_impact(PID, CID, self.gap("GAP-SRD-"), "operativo", " ")
        self.assertIn("--impact necesita --reason", str(reasonless.exception))
        self.assertNotIn("gap_impact", read_state(PID)["changes"][CID])

    def test_cli_rules(self):
        srd = self.gap("GAP-SRD-")
        for argv in (
            ["gaps", PID, "--change", CID, "--id", srd, "--impact", "operativo"],
            ["gaps", PID, "--id", srd, "--impact", "operativo", "--reason", "r"],
            ["gaps", PID, "--impact", "operativo", "--reason", "r"],
            ["gaps", PID, "--change", CID, "--id", srd],
        ):
            code, _ = run_cli(argv)
            self.assertNotEqual(code, 0, argv)
        code, out = run_cli(["gaps", PID, "--change", CID, "--id", srd, "--impact", "operativo", "--reason", "lo define Compras"])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["action"], "impact")
        self.assertEqual(result["message"], f"{CID}: {srd} queda como pendiente operativo: lo define Compras")
        self.assertEqual(result["verdict"]["deferred"], {"construccion": 1, "operativo": 1})

    def test_status_and_english(self):
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertEqual(status["verdict"]["verdict"], "NOT_READY")
        set_language(PID, "en")
        forget_read_snapshots()
        english = build_change_verdict(PID, CID)
        self.assertIn("1 blocking question(s) open", english["blockers"])
        self.assertTrue(any(b.startswith("2 deferred item(s) hold back the build") for b in
                            self.verdict(self.settled())["blockers"]))
        srd = self.gap("GAP-SRD-")
        result = set_gap_impact(PID, CID, srd, "operativo", "Purchasing owns it")
        self.assertEqual(result["message"], f"{CID}: {srd} is now a operativo deferred item: Purchasing owns it")


class Mcp(unittest.TestCase):
    def test_mcp_gaps_impact(self):
        captured: list[list[str]] = []
        with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
            _tools()["sentinel_gaps"]("P", id="GAP-SED-X", change="CHG-001", impact="operativo", reason="r")
        self.assertEqual(captured[0], ["gaps", "P", "--id", "GAP-SED-X", "--reason", "r", "--change", "CHG-001", "--impact", "operativo"])


if __name__ == "__main__":
    unittest.main()
