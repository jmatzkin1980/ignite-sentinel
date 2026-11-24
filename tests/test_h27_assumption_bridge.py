"""IMP-412 (H27 inc 4) task 2: a `supuesto` answer is the bridge to the change's assumption register."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from test_h26_cross_record import CID, PID, CrossCase  # noqa: E402

from sentinel.assumptions import load_assumptions  # noqa: E402
from sentinel.change_assumptions import load_change_assumptions  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

QUOTE = "quiero consultar quién aprobó cada alta y cuándo"
STATEMENT = "El historial del auditor se muestra como una pestaña del detalle del alta."


def _read(path: str) -> str:
    found = Path(path)
    return (found if found.is_absolute() else Path.cwd() / found).read_text(encoding="utf-8")


class Bridge(CrossCase):
    def setUp(self):
        super().setUp()
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        forget_read_snapshots()
        self.srd = next(i for i in self.gaps() if i.startswith("GAP-SRD-"))
        self.dis = next(i for i in self.gaps() if i.startswith("GAP-DIS-"))
        self.asm = "ASM-" + self.srd[4:]

    def block(self, answer: str = STATEMENT, evidence: str = f'"{QUOTE}"') -> list[str]:
        return [f"### {self.srd}", f"- Respuesta: {answer}", "- Owner / fuente: BA de Compras",
                f"- Evidencia o referencia: {evidence}", "- Estado de decisión: supuesto", "- Valida: Diseño", ""]

    def answer_file(self, *blocks: list[str]) -> Path:
        path = Path.cwd() / f"resp-{len(list(Path.cwd().glob('resp-*')))}.md"
        path.write_text("\n".join(line for block in blocks for line in block) + "\n", encoding="utf-8")
        return path

    def resolve(self, *blocks: list[str]) -> dict:
        return json.loads(run_ok(["resolve-gaps", PID, "--source", str(self.answer_file(*blocks)), "--change", CID]))

    def register(self) -> Path:
        return workspace_path(PID) / "01_discovery" / CID / "assumptions.md"

    def dis_block(self, answer: str = "Rige el pedido del área de Compras.") -> list[str]:
        return [f"### {self.dis}", f"- Respuesta: {answer}", "- Opción: B", "- Owner / fuente: Jefa de Compras",
                f"- Evidencia o referencia: {self.ids()['pedido']}:1", "- Estado de decisión: confirmado", ""]

    def test_supuesto_answer_creates_assumption(self):
        out = self.resolve(self.block())
        self.assertEqual(out["assumed"], [self.srd])
        self.assertEqual(out["assumptions"], [self.asm])
        row = self.gaps()[self.srd]
        self.assertEqual(row["status"].strip("`"), "CLOSED")
        self.assertEqual(row["closure_reason"], "assumed")
        self.assertEqual(row["resolution_note"], f"supuesto {self.asm}: a validar con Diseño")
        (found,) = load_change_assumptions(PID, CID)
        self.assertEqual((found["id"], found["status"], found["lens"], found["owner"], found["risk"]),
                         (self.asm, "ASSUMED", "design", "BA de Compras", "med"))
        self.assertEqual(found["validate_with"], "Diseño")
        self.assertEqual(out["ears_rows"], [])
        self.assertEqual(load_assumptions(PID), [])

    def test_supuesto_without_local_quote_stays_answered(self):
        out = self.resolve(self.block(evidence="lo dijo Diseño por teléfono"))
        self.assertEqual(out.get("assumed", []), [])
        row = self.gaps()[self.srd]
        self.assertEqual(row["status"].strip("`"), "ANSWERED")
        self.assertIn("una cita literal (entre comillas)", row["resolution_note"])
        self.assertFalse(self.register().exists())

    def test_supuesto_wording_is_not_flagged(self):
        out = self.resolve(
            self.block("Supuesto a validar con Diseño: el historial se muestra como una pestaña del detalle del alta."),
            self.dis_block())
        self.assertIsNone(out["unvalidated_trigger"])
        self.assertIn(self.dis, out["closed"], out)

    def test_confirmed_block_still_flagged(self):
        out = self.resolve(self.block(), self.dis_block("Rige el pedido, pendiente de validación con Diseño."))
        self.assertEqual(out["unvalidated_trigger"]["term"], "pendiente de validacion")
        self.assertIn(self.dis, out["answered"])
        self.assertNotIn(self.dis, out["closed"])

    def test_rerun_same_supuesto_is_idempotent(self):
        path = self.answer_file(self.block())
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])
        first = self.register().read_bytes()
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])
        self.assertEqual(self.gaps()[self.srd]["status"].strip("`"), "CLOSED")
        self.assertEqual(self.register().read_bytes(), first)
        self.assertEqual([r["id"] for r in load_change_assumptions(PID, CID)], [self.asm])

    def test_status_verdict_brief_export(self):
        self.resolve(self.block())
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertEqual(status["assumptions"], {"open": 1, "by_domain": {"Diseño": 1}, "ids": [self.asm]})
        self.assertIn(f"1 supuesto(s) a validar: {self.asm}", status["verdict"]["warnings"])
        self.assertFalse(any("supuesto" in b for b in status["verdict"]["blockers"]))
        brief = json.loads(run_ok(["brief", PID, "--change", CID]))
        text = _read(brief["path"])
        self.assertIn("**Supuestos a validar**", text)
        self.assertIn(f"| {self.asm} | {STATEMENT} | Diseño | {self.srd} |", text)
        out = json.loads(run_ok(["export", PID, "--artifact", "brief", "--change", CID]))
        exported = _read(out["path"])
        self.assertIn(f"`{self.asm}` — {STATEMENT} — a validar con Diseño (ASSUMED)", exported)
        self.assertIn("> **Supuestos:** 1", exported)

    def test_old_change_has_no_new_keys(self):
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertNotIn("assumptions", status)
        self.assertNotIn("delegated", status)
        brief = json.loads(run_ok(["brief", PID, "--change", CID]))
        self.assertNotIn("Supuestos a validar", _read(brief["path"]))
        out = json.loads(run_ok(["export", PID, "--artifact", "brief", "--change", CID]))
        self.assertIn("> **Supuestos:** 0", _read(out["path"]))


class ProjectPath(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        run_ok(["init", "BRGP"])
        run_ok(["ingest", "BRGP", "--source", str(Path(__file__).resolve().parent / "fixtures" / "incomplete_requirement.md")])

    def test_project_supuesto_unchanged(self):
        base = workspace_path("BRGP")
        lines = (base / "01_discovery" / "gaps.md").read_text(encoding="utf-8").splitlines()
        gap_id = next(line.split("|")[1].strip() for line in lines if line.startswith("| GAP-"))
        path = Path.cwd() / "resp.md"
        path.write_text(f"### {gap_id}\n- Respuesta: {STATEMENT}\n- Owner / fuente: BA de Compras\n"
                        f"- Evidencia o referencia: \"{QUOTE}\"\n- Estado de decisión: supuesto\n- Valida: Diseño\n",
                        encoding="utf-8")
        run_ok(["resolve-gaps", "BRGP", "--source", str(path)])
        text = (base / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if line.startswith(f"| {gap_id} "))
        self.assertIn("PARTIALLY_CLOSED", row)
        self.assertIn("ambiguous: answer present but no recognizable decision status", row)
        self.assertFalse((base / "01_discovery" / "assumptions.md").exists())


if __name__ == "__main__":
    unittest.main()
