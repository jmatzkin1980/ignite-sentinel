"""IMP-396: escalation warnings of a change: the runtime warns, the BA decides."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from sentinel.change_escalation import escalation_warnings  # noqa: E402
from sentinel.change_requirements import change_requirements_path  # noqa: E402
from sentinel.changes import confirm_border  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HEADER = ("| ID | Pattern | Delta | Statement | Source | Afecta | Superficie |\n"
          "| --- | --- | --- | --- | --- | --- | --- |\n")
SUGGEST_ES = "El BA decide: partir el cambio o pasar al camino de proyecto"
SUGGEST_EN = "The BA decides: split the change or move to the project path"


def item(zone: str, kind: str, name: str) -> dict:
    return {"zone": zone, "type": kind, "name": name, "cite": "pedido"}


def table(rows: list[tuple[str, str, str]]) -> str:
    body = "".join(
        f"| REQ-EARS-{i:03d} | event | {delta} | Cuando A, el sistema debe B. | `GAP-ACCEPTANCE` / `CHG-001` | - | {surf} |\n"
        for i, (_, delta, surf) in enumerate(rows, 1))
    return "# Requisitos del cambio CHG-001\n\n## Normalized Requirements (EARS)\n\n" + HEADER + body


class ChangeEscalation(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "BORR"])
        out = json.loads(run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"]))
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", out["change_id"]])

    def setup_change(self, border: list[dict], rows: list[tuple[str, str, str]] = ()):
        confirm_border("BORR", "CHG-001", border)
        path = change_requirements_path(workspace_path("BORR"), "CHG-001")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(table(list(rows)), encoding="utf-8")

    def test_fixture_border_has_no_warnings(self):
        self.assertEqual(escalation_warnings("BORR", "CHG-001"), [])

    def test_several_processes(self):
        self.setup_change([item("nuevo", "proceso", "Alta"), item("preservado", "proceso", "Baja")])
        (w,) = escalation_warnings("BORR", "CHG-001")
        self.assertEqual(w["trigger"], "several_processes")
        self.assertEqual(w["surfaces"], ["Alta", "Baja"])
        self.assertEqual(w["rows"], [])
        self.assertTrue(w["message"].endswith(SUGGEST_ES))

    def test_integration_in_new_or_adjacent_zone(self):
        self.setup_change([item("adyacente", "integracion", "Pasarela")])
        (w,) = escalation_warnings("BORR", "CHG-001")
        self.assertEqual((w["trigger"], w["surfaces"]), ("several_processes", ["Pasarela"]))
        self.setup_change([item("preservado", "integracion", "Pasarela")])
        self.assertEqual(escalation_warnings("BORR", "CHG-001"), [])

    def test_new_actors(self):
        self.setup_change([item("nuevo", "rol", "Auditor"), item("adyacente", "rol", "Jefa")])
        (w,) = escalation_warnings("BORR", "CHG-001")
        self.assertEqual((w["trigger"], w["surfaces"]), ("new_actors", ["Auditor"]))

    def test_third_party_contract(self):
        self.setup_change(
            [item("adyacente", "endpoint", "API de pagos"), item("nuevo", "pantalla", "Panel")],
            [("", "ADDED", "API de pagos"), ("", "MODIFIED", "API de pagos"), ("", "REMOVED", "Panel; API de pagos")])
        (w,) = escalation_warnings("BORR", "CHG-001")
        self.assertEqual(w["trigger"], "third_party_contract")
        self.assertEqual(w["surfaces"], ["API de pagos"])
        self.assertEqual(w["rows"], ["REQ-EARS-002", "REQ-EARS-003"])

    def test_added_only_does_not_trigger_third_party(self):
        self.setup_change([item("adyacente", "endpoint", "API de pagos")], [("", "ADDED", "API de pagos")])
        self.assertEqual(escalation_warnings("BORR", "CHG-001"), [])

    def test_order_without_duplicates(self):
        self.setup_change(
            [item("nuevo", "proceso", "A"), item("nuevo", "proceso", "B"), item("nuevo", "rol", "R"),
             item("adyacente", "endpoint", "E")], [("", "MODIFIED", "E")])
        got = [w["trigger"] for w in escalation_warnings("BORR", "CHG-001")]
        self.assertEqual(got, ["several_processes", "new_actors", "third_party_contract"])

    def test_english_message(self):
        self.setup_change([item("nuevo", "rol", "Auditor")])
        from sentinel.workspace import update_state, read_state  # noqa: E402
        changes = {k: dict(v) for k, v in read_state("BORR")["changes"].items()}
        changes["CHG-001"]["language"] = "en"
        update_state("BORR", changes=changes)
        (w,) = escalation_warnings("BORR", "CHG-001")
        self.assertTrue(w["message"].endswith(SUGGEST_EN))
        self.assertNotIn("El BA decide", w["message"])


class ChangeEscalationOpenBorder(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])

    def test_unconfirmed_border_returns_nothing(self):
        self.assertEqual(escalation_warnings("BORR", "CHG-001"), [])


if __name__ == "__main__":
    unittest.main()
