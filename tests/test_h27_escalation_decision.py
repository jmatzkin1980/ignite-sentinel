"""T2-05 (IMP-412): the escalation warning records the BA's decision and its threshold follows the request size."""
from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.change_escalation import escalation_threshold, escalation_warnings  # noqa: E402
from sentinel.change_requirements import change_requirements_path  # noqa: E402
from sentinel.changes import confirm_border  # noqa: E402
from sentinel.readiness_verdict import build_change_verdict  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CID = "CHG-001"
EMPTY_EARS = ("# Requisitos del cambio CHG-001\n\n## Normalized Requirements (EARS)\n\n"
              "| ID | Pattern | Delta | Statement | Source | Afecta | Superficie |\n"
              "| --- | --- | --- | --- | --- | --- | --- |\n")


def item(zone: str, kind: str, name: str) -> dict:
    return {"zone": zone, "type": kind, "name": name, "cite": "pedido"}


def run_refused(argv: list[str]) -> tuple[int, str]:
    """Exit code and the refusal text (stdout + stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue() + err.getvalue()


def processes(n: int) -> list[dict]:
    return [item("nuevo", "proceso", f"P{i}") for i in range(n)]


class EscalationDecision(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "BORR"])
        out = json.loads(run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"]))
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", out["change_id"]])

    def setup_border(self, border: list[dict]):
        confirm_border("BORR", CID, border)
        path = change_requirements_path(workspace_path("BORR"), CID)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(EMPTY_EARS, encoding="utf-8")

    def test_threshold(self):
        self.assertEqual(escalation_threshold(10), 2)
        self.assertEqual(escalation_threshold(260), 6)
        self.assertEqual(escalation_threshold(81), 2)

    def test_release_sized_request(self):
        with mock.patch("sentinel.change_escalation.request_element_count", return_value=260):
            self.setup_border(processes(5))
            self.assertEqual(escalation_warnings("BORR", CID), [])
            self.setup_border(processes(6))
            (w,) = escalation_warnings("BORR", CID)
        self.assertEqual((w["count"], w["threshold"]), (6, 6))
        self.assertIn("para un pedido de 260 elementos (umbral 6)", w["message"])

    def test_small_request(self):
        self.setup_border(processes(2))
        (w,) = escalation_warnings("BORR", CID)
        self.assertEqual(w["threshold"], 2)

    def test_keep_single_silences(self):
        self.setup_border(processes(2))
        run_ok(["sources", "BORR", "--change", CID, "--keep-single", "--reason", "el release sale junto"])
        self.assertEqual(escalation_warnings("BORR", CID), [{
            "trigger": "kept_single", "surfaces": [], "rows": [], "decided": True,
            "message": "decidido: sigue como un cambio (el release sale junto)"}])
        verdict = build_change_verdict("BORR", CID)
        self.assertFalse(any("decidido" in w or "El borde del cambio" in w for w in verdict["warnings"]))
        status = json.loads(run_ok(["status", "BORR", "--change", CID]))
        self.assertEqual(sum(1 for w in status["warnings"] if w["trigger"] == "kept_single"), 1)

    def test_new_trigger_after_decision_still_warns(self):
        self.setup_border(processes(2))
        run_ok(["sources", "BORR", "--change", CID, "--keep-single", "--reason", "el release sale junto"])
        self.setup_border([*processes(2), item("nuevo", "rol", "Auditor")])
        self.assertEqual([w["trigger"] for w in escalation_warnings("BORR", CID)], ["kept_single", "new_actors"])

    def test_keep_single_refusals(self):
        self.setup_border(processes(2))
        code, out = run_refused(["sources", "BORR", "--change", CID, "--keep-single"])
        self.assertEqual(code, 3)
        self.assertIn("necesita --reason", out)
        code, _ = run_cli(["sources", "BORR", "--keep-single", "--reason", "x"])
        self.assertNotEqual(code, 0)
        self.setup_border([item("preservado", "proceso", "Alta")])
        code, out = run_refused(["sources", "BORR", "--change", CID, "--keep-single", "--reason", "x"])
        self.assertEqual(code, 3)
        self.assertIn("no tiene avisos de escalamiento que decidir", out)

    def test_unknown_change_is_a_gate_refusal(self):
        code, _ = run_cli(["sources", "BORR", "--change", "CHG-099", "--keep-single", "--reason", "x"])
        self.assertEqual(code, 4)


if __name__ == "__main__":
    unittest.main()
