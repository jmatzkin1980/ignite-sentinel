"""IMP-412 (H27 inc 4) task 3: confirmation on behalf of the BA, with its trace."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402
from test_h26_cross_record import CID as CCID, PID as CPID, CrossCase  # noqa: E402
from test_h26_extract_proposals import (  # noqa: E402
    CID, EXAMPLE, GOOD_STATEMENT, OK_FIELDS, PID, RN02_QUOTE, ProposalsCase, block,
)

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.delegation import delegations_path, is_delegated  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.extraction.confirm import confirm_item  # noqa: E402
from sentinel.extraction.proposals import load_proposals, record_proposals  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

NOTE = "el BA delegó la extracción completa"


def _read(path: str) -> str:
    found = Path(path)
    return (found if found.is_absolute() else Path.cwd() / found).read_text(encoding="utf-8")


class Unit(unittest.TestCase):
    def test_is_delegated(self):
        for text in ("delegación del BA", "Delegado", "delegated by the BA"):
            self.assertTrue(is_delegated(text), text)
        for text in ("", "la jefa de Compras", "BA"):
            self.assertFalse(is_delegated(text), text)


class Extraction(ProposalsCase):
    def setUp(self):
        super().setUp()
        record_proposals(PID, CID, EXAMPLE)

    def items(self) -> dict:
        return load_proposals(workspace_path(PID), CID)["items"]

    def test_confirm_all_delegated(self):
        out = json.loads(run_ok(["extract", PID, "--change", CID, "--confirm", "all", "--delegated", "--note", NOTE]))
        self.assertTrue(out["confirmed"])
        self.assertEqual(out["delegated"], out["confirmed"])
        items = self.items()
        for element_id in out["confirmed"]:
            self.assertEqual(items[element_id]["confirmed_by"], "delegated")
            self.assertEqual(items[element_id]["delegated_note"], NOTE)
            self.assertTrue(items[element_id]["delegated_at"])
        self.assertEqual(out["held"], ["RN-04"])
        self.assertEqual(items["RN-04"]["status"], "proposed")
        self.assertIn("por delegación (revisar)", out["message"])
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertEqual(sorted(status["delegated"]["elements"]), sorted(out["confirmed"]))
        self.assertEqual(status["delegated"]["total"], len(out["confirmed"]))

    def test_confirm_without_delegation_is_unchanged(self):
        out = json.loads(run_ok(["extract", PID, "--change", CID, "--confirm", "all"]))
        self.assertNotIn("delegated", out)
        self.assertNotIn("por delegación", out["message"])
        self.assertTrue(all("confirmed_by" not in item for item in self.items().values()))
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertNotIn("delegated", status)

    def test_partial_read_stays_refused(self):
        path = Path.cwd() / "parcial.md"
        path.write_text(block("RN-02", "- Tratamiento: requisito", "- Lectura: parcial", RN02_QUOTE,
                              GOOD_STATEMENT, *OK_FIELDS), encoding="utf-8")
        record_proposals(PID, CID, path)
        with self.assertRaises(InputError) as caught:
            confirm_item(PID, CID, "RN-02", delegated=True)
        self.assertIn("declara Lectura: parcial", str(caught.exception))
        self.assertEqual(self.items()["RN-02"]["status"], "proposed")

    def test_ba_ratifies(self):
        run_ok(["extract", PID, "--change", CID, "--confirm", "all", "--delegated"])
        result = confirm_item(PID, CID, "HU-01")
        self.assertEqual(result["ratified"], ["HU-01"])
        self.assertEqual(result["action"], "confirm")
        item = self.items()["HU-01"]
        self.assertEqual(item["status"], "confirmed")
        for key in ("confirmed_by", "delegated_note", "delegated_at"):
            self.assertNotIn(key, item)
        with self.assertRaises(InputError) as caught:
            confirm_item(PID, CID, "HU-01")
        self.assertIn("no tiene una propuesta pendiente de confirmar", str(caught.exception))
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertNotIn("HU-01", status["delegated"]["elements"])

    def test_guards(self):
        code, _ = run_cli(["extract", PID, "--change", CID, "--confirm", "all", "--note", "x"])
        self.assertNotEqual(code, 0)
        proposals = Path.cwd() / "p.md"
        proposals.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        code, _ = run_cli(["extract", PID, "--change", CID, "--proposals", str(proposals), "--delegated"])
        self.assertNotEqual(code, 0)

    def test_brief_and_seal_list_delegated(self):
        out = json.loads(run_ok(["extract", PID, "--change", CID, "--confirm", "all", "--delegated"]))
        brief = json.loads(run_ok(["brief", PID, "--change", CID]))
        text = _read(brief["path"])
        self.assertIn("**Confirmado por delegación (revisar)**", text)
        for element_id in out["confirmed"]:
            self.assertIn(f"- {element_id}", text)
        exported = _read(json.loads(run_ok(["export", PID, "--artifact", "brief", "--change", CID]))["path"])
        self.assertIn(f"> **Confirmado por delegación:** {len(out['confirmed'])} (revisar: ", exported)


class GapDelegation(CrossCase):
    def setUp(self):
        super().setUp()
        record_cross(CPID, CCID, "diseno", self.write("cruce_diseno.md"))
        forget_read_snapshots()
        self.dis = next(i for i in self.gaps() if i.startswith("GAP-DIS-"))

    def answer(self, *extra: str) -> dict:
        path = Path.cwd() / "resp-dis.md"
        lines = [f"### {self.dis}", "- Respuesta: Rige el pedido del área de Compras.", "- Opción: B",
                 "- Owner / fuente: Jefa de Compras", f"- Evidencia o referencia: {self.ids()['pedido']}:1",
                 "- Estado de decisión: confirmado", *extra, ""]
        path.write_text("\n".join(lines), encoding="utf-8")
        return json.loads(run_ok(["resolve-gaps", CPID, "--source", str(path), "--change", CCID]))

    def test_gap_delegation_from_response(self):
        out = self.answer("- Confirmado por: delegación del BA")
        self.assertIn(self.dis, out["closed"])
        self.assertEqual(out["delegated"], [self.dis])
        data = json.loads(delegations_path(workspace_path(CPID), CCID).read_text(encoding="utf-8"))
        self.assertEqual(data["gaps"][self.dis]["note"], "delegación del BA")
        self.assertTrue(data["gaps"][self.dis]["at"] and data["gaps"][self.dis]["response"])
        status = json.loads(run_ok(["status", CPID, "--change", CCID]))
        self.assertEqual(status["delegated"], {"elements": [], "gaps": [self.dis], "total": 1})
        run_ok(["brief", CPID, "--change", CCID])
        exported = _read(json.loads(run_ok(["export", CPID, "--artifact", "brief", "--change", CCID]))["path"])
        self.assertIn(f"> **Confirmado por delegación:** 1 (revisar: {self.dis})", exported)

    def test_confirmed_by_the_ba_leaves_no_trace(self):
        out = self.answer("- Confirmado por: la jefa de Compras")
        self.assertIn(self.dis, out["closed"])
        self.assertNotIn("delegated", out)
        self.assertFalse(delegations_path(workspace_path(CPID), CCID).exists())
        status = json.loads(run_ok(["status", CPID, "--change", CCID]))
        self.assertNotIn("delegated", status)


class ProjectPath(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        run_ok(["init", "BRGD"])
        run_ok(["ingest", "BRGD", "--source", str(Path(__file__).resolve().parent / "fixtures" / "incomplete_requirement.md")])

    def test_project_ignores_confirmed_by(self):
        base = workspace_path("BRGD")
        lines = (base / "01_discovery" / "gaps.md").read_text(encoding="utf-8").splitlines()
        gap_id = next(line.split("|")[1].strip() for line in lines if line.startswith("| GAP-"))
        path = Path.cwd() / "resp.md"
        path.write_text(f"### {gap_id}\n- Respuesta: Rige el pedido del área de Compras.\n- Owner / fuente: Jefa de Compras\n"
                        "- Evidencia o referencia: pedido de Compras\n- Estado de decisión: confirmado\n"
                        "- Confirmado por: delegación del BA\n", encoding="utf-8")
        run_ok(["resolve-gaps", "BRGD", "--source", str(path)])
        text = (base / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if line.startswith(f"| {gap_id} "))
        self.assertIn("CLOSED", row)
        self.assertEqual(list(base.rglob("delegations.json")), [])


if __name__ == "__main__":
    unittest.main()
