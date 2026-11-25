"""IMP-414 (H27 inc 5a) task 3: the control table of the consolidation, --keep-text and the final export that waits."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
import test_change_next  # noqa: E402
import test_h27_consolidation  # noqa: E402
from test_h26_cross_record import CID, PID  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.consolidation_control import (  # noqa: E402
    consolidation_control, consolidation_sha, keeps_request, retires, write_consolidation_control,
)
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.readiness_verdict import change_next_step  # noqa: E402
from sentinel.workspace import read_json, workspace_path  # noqa: E402


def run_err(argv: list[str]) -> tuple[int, str]:
    """Exit code and stderr (run_cli drops it)."""
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


def row_of(element: str) -> dict:
    return next(r for r in consolidation_control(PID, CID)["rows"] if r["element"] == element)


class Control(test_h27_consolidation.ConsolidationCase):
    def test_keeps_request(self):
        element = {"id": "RN-02", "source_id": "F-01", "lines": [31, 31]}
        self.assertTrue(keeps_request({"id": "GAP-DIS-AAAA0001", "option": "B"}, element))
        self.assertFalse(keeps_request({"id": "GAP-DIS-AAAA0001", "option": "A"}, element))
        self.assertFalse(keeps_request({"id": "GAP-DIS-AAAA0001"}, element))
        self.assertTrue(retires({"id": "GAP-SRD-AAAA0001", "option": "C"}))
        self.assertFalse(retires({"id": "GAP-SRD-AAAA0001", "option": "A"}))
        cites = [{"side": "pedido", "line": 31, "source_id": "F-01"}, {"side": "pedido", "line": 45, "source_id": "F-01"}]
        decision = {"id": "GAP-CON-AAAA0001", "option": "A", "citations": cites}
        self.assertTrue(keeps_request(decision, element))
        self.assertFalse(keeps_request(decision, {"id": "RN-04", "source_id": "F-01", "lines": [45, 45]}))

    def test_pending_until_replaced(self):
        row = row_of("RN-02")
        self.assertEqual((row["status"], row["gaps"]), ("pendiente", [self.dis]))
        self.assertIn("falta reemplazo o --keep-text", row["reason"])
        discarded = row_of("RN-06")
        self.assertEqual(discarded["status"], "excluido")
        self.assertEqual(discarded["reason"], "Los proveedores del exterior quedan fuera de este cambio.")
        self.submit_text(self.rep())
        control = consolidation_control(PID, CID)
        self.assertIn("RN-02", control["unconfirmed"])
        self.assertEqual(row_of("RN-02")["status"], "pendiente")
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
        row = row_of("RN-02")
        self.assertEqual((row["status"], row["replacement"]), ("modificado", "REP-RN-02"))
        self.assertEqual(consolidation_control(PID, CID)["unconfirmed"], [])

    def test_keep_text(self):
        argv = ["extract", PID, "--change", CID, "--keep-text", "RN-02", "--gap", self.dis]
        forget_read_snapshots()
        code, err = run_err(argv)
        self.assertEqual(code, 3, err)
        self.assertIn("necesita --reason", err)
        forget_read_snapshots()
        result = json.loads(run_ok([*argv, "--reason", "El texto queda; el umbral sale del parámetro"]))
        self.assertEqual((result["action"], result["element"], result["gap"]), ("keep_text", "RN-02", self.dis))
        self.assertEqual(row_of("RN-02")["status"], "incluido")
        self.assertIn("RN-02", self.stored()["kept"])

    def test_keeping_option_needs_nothing(self):
        self.answer(self.dis, "Rige el pedido: el umbral es 5.000.000.", "B")
        self.assertEqual(row_of("RN-02")["status"], "incluido")
        forget_read_snapshots()
        code, err = run_err(["extract", PID, "--change", CID, "--keep-text", "RN-02", "--gap", self.dis, "--reason", "x"])
        self.assertEqual(code, 3, err)
        self.assertIn("ya conserva el texto del pedido", err)
        result = self.submit_text(self.rep())
        self.assertEqual(result["recorded"], [], result)
        reasons = [r for rs in result["rejected"].values() for r in rs]
        self.assertTrue(any("conserva el texto del pedido" in r for r in reasons), reasons)

    def test_control_files_and_status(self):
        path = write_consolidation_control(PID, CID)
        self.assertEqual(path, workspace_path(PID) / "01_discovery" / CID / "consolidation_control.md")
        text = path.read_text(encoding="utf-8")
        self.assertIn("> Interno: no forma parte del entregable.", text)
        self.assertIn("| RN-02 | pendiente |", text)
        todo = text.split("## Para consolidar")[1]
        self.assertIn("### RN-02", todo)
        self.assertIn(f"- Decisión: {self.dis}", todo)
        self.assertIn("- Líneas: 31-31", todo)
        self.assertTrue(path.with_suffix(".json").is_file())
        self.submit_text(self.rep())
        forget_read_snapshots()
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertGreaterEqual(status["consolidation"]["excluido"], 1)
        self.assertEqual(status["consolidation"]["unconfirmed"], ["RN-02"])
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
        text = path.read_text(encoding="utf-8")
        self.assertIn("| RN-02 | modificado |", text)
        self.assertNotIn("### RN-02", text)
        self.assertEqual(len(consolidation_sha(PID, CID)), 16)

    def test_sha_moves_with_the_text(self):
        before = consolidation_sha(PID, CID)
        self.submit_text(self.rep())
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
        self.assertNotEqual(consolidation_sha(PID, CID), before)

    def step_key(self) -> str:
        from sentinel.changes import get_change
        from sentinel.readiness_verdict import _change_step_key

        return _change_step_key(PID, CID, get_change(PID, CID))

    def earlier_gates_done(self) -> ExitStack:
        """The steps before `consolidate` (borders, cross-reads, extraction, brief, EARS rows) stand as done."""
        from sentinel import changes
        from sentinel.extraction import coverage

        real_change, real_cover = changes.get_change, coverage.extraction_coverage

        def change(project_id, change_id):
            found = dict(real_change(project_id, change_id))
            found["gap_counts"] = {**(found.get("gap_counts") or {}), "blocking_open": 0}
            return found

        def cover(project_id, change_id):
            return {**real_cover(project_id, change_id), "pending": 0, "proposed": 0, "orphans": [], "unreadable": []}

        stack = ExitStack()
        for target, value in (
            ("sentinel.readiness_verdict._has_baseline", True),
            ("sentinel.readiness_verdict._brief_state", ""),
            ("sentinel.readiness_verdict._has_unit_rows", True),
            ("sentinel.crosses.state.cross_status", {"missing": []}),
            ("sentinel.crosses.surfaces.new_surface_candidates", []),
            ("sentinel.change_coherence.coherence_state", {"state": "current"}),
            ("sentinel.extraction.verify.verification_needed", {"needed": False}),
            ("sentinel.extraction.coverage.preserved_coverage", {"missing": []}),
        ):
            stack.enter_context(patch(target, return_value=value))
        stack.enter_context(patch("sentinel.changes.get_change", side_effect=change))
        stack.enter_context(patch("sentinel.extraction.coverage.extraction_coverage", side_effect=cover))
        return stack

    def test_next_step(self):
        self.submit_text(self.rep())
        with self.earlier_gates_done():
            self.assertEqual(self.step_key(), "consolidate_confirm")
            step = change_next_step(PID, CID)
            self.assertEqual(step["key"], "consolidate_confirm")
            self.assertIn("--confirm-replacement RN-02", step["command"])
            forget_read_snapshots()
            run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
            # the mocked gates lie about the extraction: its unconfirmed elements still wait, but no replacement does
            self.assertEqual(self.step_key(), "consolidate")
            self.assertEqual(consolidation_control(PID, CID)["unconfirmed"], [])

    def test_final_refused_while_pending(self):
        run_ok(["brief", PID, "--change", CID])
        forget_read_snapshots()
        # the earlier gates (sections still to extract, pending marks) say their own thing; the one under test is next
        with patch("sentinel.deliverables.gate", return_value={"deliverable": "final", "pending_marks": 0}):
            code, err = run_err(["export", PID, "--artifact", "brief", "--change", CID, "--final"])
        self.assertNotEqual(code, 0)
        self.assertIn("sin consolidar", err)
        self.assertIn("RN-02", err)
        self.assertIsNone(read_json(workspace_path(PID) / "state.json", {})["changes"][CID].get("final_export"))


class OldChange(test_change_next.ChangeNextSequence):
    def test_each_row_of_the_table_in_order(self):
        super().test_each_row_of_the_table_in_order()
        status = json.loads(run_ok(["status", "BORR", "--change", CID]))
        self.assertEqual(status["next_action"]["key"], "done")
        self.assertEqual(status["consolidation"]["pendiente"], 0)
        consolidation = workspace_path("BORR") / "02_requirements" / CID / "extraction" / "consolidation.json"
        self.assertFalse(consolidation.exists())


if __name__ == "__main__":
    unittest.main()
