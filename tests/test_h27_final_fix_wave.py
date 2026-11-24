"""IMP-412 (H27 inc 4) final fix wave: regressions of the whole-branch review (C1, I1-I7, M-items, P1-P3)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_cli, run_ok  # noqa: E402
from test_h26_cross_record import CID, PID  # noqa: E402
import test_h27_assumption_bridge as bridge_tests  # noqa: E402
import test_h27_decision_conflicts as clash_tests  # noqa: E402
import test_h27_escalation_decision as escalation_tests  # noqa: E402
import test_h27_extension_speculative as speculative_tests  # noqa: E402
import test_h27_review_views as review_tests  # noqa: E402

QUOTE, STATEMENT = bridge_tests.QUOTE, bridge_tests.STATEMENT
ECID, processes, run_refused = escalation_tests.CID, escalation_tests.processes, escalation_tests.run_refused
PID_S, CID_S = speculative_tests.PID, speculative_tests.CID

from sentinel.change_assumptions import load_change_assumptions  # noqa: E402
from sentinel.change_escalation import escalation_warnings  # noqa: E402
from sentinel.change_requirements import load_change_ears, reconcile_extraction_ears  # noqa: E402
from sentinel.changes import change_gaps_path  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import _save_change_gaps  # noqa: E402
from sentinel.decision_conflicts import conflicting_pairs  # noqa: E402
from sentinel.decision_memory import closed_decisions  # noqa: E402
from sentinel.delegation import delegated_summary  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402


def _silence(case: type, keep: set[str] = frozenset()) -> None:
    """The subclass reuses the parent's workspace, not its tests."""
    for name in [n for n in dir(case) if n.startswith("test_") and n not in keep]:
        setattr(case, name, None)


def _read(path: str) -> str:
    found = Path(path)
    return (found if found.is_absolute() else Path.cwd() / found).read_text(encoding="utf-8")


class AssumptionLifecycle(bridge_tests.Bridge):
    def test_rerun_after_invalidate_stays_open(self):  # C1
        path = self.answer_file(self.block())
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])
        forget_read_snapshots()
        run_ok(["assume", PID, "--change", CID, "--id", self.asm, "--invalidate", "--reason", "Diseño no acepta"])
        forget_read_snapshots()
        self.assertEqual(self.gaps()[self.srd]["status"].strip("`"), "OPEN")
        out = json.loads(run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID]))
        forget_read_snapshots()
        row = self.gaps()[self.srd]
        self.assertEqual(row["status"].strip("`"), "OPEN")
        self.assertNotEqual(row.get("closure_reason"), "assumed")
        self.assertEqual([r["status"] for r in load_change_assumptions(PID, CID)], ["INVALIDATED"])
        self.assertTrue(any("INVALIDATED" in finding for finding in out["closure_findings"]), out["closure_findings"])
        self.assertNotIn("assumed", out)

    def test_rerun_after_validate_keeps_it_closed(self):  # I1
        path = self.answer_file(self.block())
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])
        forget_read_snapshots()
        run_ok(["assume", PID, "--change", CID, "--id", self.asm, "--validate", "--reason", "Diseño ok"])
        forget_read_snapshots()
        before = self.gaps()[self.srd]
        out = json.loads(run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID]))
        forget_read_snapshots()
        row = self.gaps()[self.srd]
        self.assertEqual((row["status"].strip("`"), row["closure_reason"]), ("CLOSED", "answered"))
        self.assertEqual(row["resolution_note"], before["resolution_note"])
        self.assertNotIn(self.srd, out["answered"])

    def test_supuesto_block_on_a_confirmed_decision_changes_nothing(self):  # I1
        self.resolve(self.dis_block())
        forget_read_snapshots()
        before = self.gaps()[self.dis]
        block = [f"### {self.dis}", f"- Respuesta: {STATEMENT}", "- Owner / fuente: BA de Compras",
                 f'- Evidencia o referencia: "{QUOTE}"', "- Estado de decisión: supuesto", "- Valida: Diseño", ""]
        out = self.resolve(block)
        forget_read_snapshots()
        row = self.gaps()[self.dis]
        self.assertEqual((row["status"].strip("`"), row.get("closure_reason")), ("CLOSED", before.get("closure_reason")))
        self.assertEqual(row.get("resolution_note"), before.get("resolution_note"))
        self.assertIn(self.dis, " ".join(out["closure_findings"]))

    def test_unquoted_evidence_does_not_close(self):  # I2
        out = self.resolve(self.block(evidence="Diseño"))
        row = self.gaps()[self.srd]
        self.assertEqual(row["status"].strip("`"), "ANSWERED")
        self.assertEqual(out.get("assumed", []), [])
        self.assertFalse(self.register().exists())

    def test_short_quote_does_not_close(self):  # I2
        out = self.resolve(self.block(evidence='"alta"'))
        self.assertEqual(self.gaps()[self.srd]["status"].strip("`"), "ANSWERED")
        self.assertEqual(out.get("assumed", []), [])
        self.assertFalse(self.register().exists())

    def asm_file(self, justification: str, gap: str) -> Path:
        path = Path.cwd() / f"asm-{len(list(Path.cwd().glob('asm-*')))}.json"
        path.write_text(json.dumps({"assumptions": [{
            "id": "ASM-X", "lens": "design", "statement": "El detalle muestra el historial.", "owner": "BA de Compras",
            "risk": "med", "uncertainty": "med", "justification": justification, "closes_gap": gap}]}), encoding="utf-8")
        return path

    def test_assume_change_short_justification_refused(self):  # I2
        code, out = run_refused(["assume", PID, "--change", CID, "--source", str(self.asm_file("alta", self.dis))])
        self.assertNotEqual(code, 0)
        self.assertIn("4 palabras", out)

    def test_assume_change_cannot_cite_an_archived_answer_file(self):  # I3
        invented = "esta frase la inventó el agente y no está en ninguna fuente"
        # an answer for an unknown id is archived with the other answer files and applied nowhere
        self.resolve(["### GAP-ZZZ-0001", f"- Respuesta: {invented}", "- Estado de decisión: confirmado", ""])
        forget_read_snapshots()
        base = workspace_path(PID)
        holders = [p for p in base.rglob("*") if p.is_file() and p.suffix in (".md", ".json", ".txt")
                   and invented in p.read_text(encoding="utf-8", errors="ignore")
                   and "00_client_responses" not in p.parts and "memory.lancedb" not in p.parts]
        self.assertEqual(holders, [])
        code, out = run_refused(["assume", PID, "--change", CID, "--source", str(self.asm_file(invented, self.dis))])
        self.assertNotEqual(code, 0, out)
        self.assertIn("verbatim", out)

    def test_assume_change_refuses_gap_scope(self):  # M6
        code, out = run_refused(["assume", PID, "--change", CID, "--source", str(self.asm_file(QUOTE, "GAP-SCOPE"))])
        self.assertNotEqual(code, 0)
        self.assertIn("GAP-SCOPE", out)

    def test_assumed_closure_is_not_a_fact_in_brief_and_export(self):  # P1
        self.resolve(self.block())
        forget_read_snapshots()
        brief = json.loads(run_ok(["brief", PID, "--change", CID]))
        text = _read(brief["path"])
        self.assertNotIn(f"{STATEMENT} ({self.srd})", text)
        self.assertIn(self.asm, text)
        self.assertIn("Supuestos a validar", text)
        exported = _read(json.loads(run_ok(["export", PID, "--artifact", "brief", "--change", CID]))["path"])
        self.assertNotIn(f"(`{self.srd}`)", exported)
        self.assertIn(self.asm, exported)

    def test_assumed_from_assume_command_never_shows_placeholder(self):  # P1
        code, _ = run_cli(["assume", PID, "--change", CID, "--source", str(self.asm_file(QUOTE, self.srd))])
        self.assertEqual(code, 0)
        forget_read_snapshots()
        text = _read(json.loads(run_ok(["brief", PID, "--change", CID]))["path"])
        self.assertNotIn("respuesta confirmada sin texto", text)
        exported = _read(json.loads(run_ok(["export", PID, "--artifact", "brief", "--change", CID]))["path"])
        self.assertNotIn("respuesta confirmada sin texto", exported)

    def test_delegated_answer_without_owner_shows_in_decisiones(self):  # I5
        blk = [f"### {self.dis}", "- Respuesta: Rige el pedido del área de Compras.", "- Opción: B",
               f"- Evidencia o referencia: {self.ids()['pedido']}:1", "- Estado de decisión: confirmado",
               "- Confirmado por: delegación del BA", ""]
        out = self.resolve(blk)
        self.assertEqual(out["delegated"], [self.dis])
        forget_read_snapshots()
        exported = _read(json.loads(run_ok(["export", PID, "--artifact", "decisiones", "--change", CID]))["path"])
        self.assertIn("Decidió: BA (sin nombre)", exported)
        self.assertIn("confirmado por delegación del BA", exported)

    def delegated_block(self) -> list[str]:
        return self.dis_block()[:-1] + ["- Confirmado por: delegación del BA", ""]

    def test_ba_answering_again_ratifies_the_delegation(self):  # I6
        self.resolve(self.delegated_block())
        forget_read_snapshots()
        self.assertEqual(delegated_summary(PID, CID)["gaps"], [self.dis])
        self.resolve(self.dis_block())
        forget_read_snapshots()
        self.assertEqual(delegated_summary(PID, CID)["gaps"], [])
        exported = _read(json.loads(run_ok(["export", PID, "--artifact", "decisiones", "--change", CID]))["path"])
        self.assertNotIn("confirmado por delegación del BA", exported)

    def test_reopened_delegated_gap_is_not_listed(self):  # I6
        self.resolve(self.delegated_block())
        forget_read_snapshots()
        path = change_gaps_path(workspace_path(PID), CID)
        rows = [g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g.get("id") != "NONE"]
        for row in rows:
            if row["id"] == self.dis:
                row["status"] = "OPEN"
        _save_change_gaps(PID, CID, path, rows)
        forget_read_snapshots()
        self.assertEqual(delegated_summary(PID, CID)["gaps"], [])
        self.assertEqual(delegated_summary(PID, CID)["total"], 0)


_silence(AssumptionLifecycle, {n for n in dir(AssumptionLifecycle) if n.startswith("test_") and n in AssumptionLifecycle.__dict__})


class ClashResolution(clash_tests.ClashCase):
    def losing(self) -> tuple[str, str, str, dict[str, str]]:
        first, second, result = self.clash()
        chq = result["decision_conflicts"][0]
        texts = {first: "Rige el pedido: el umbral es 5.000.000.", second: "Rige el diseño: se puede delegar la aprobación."}
        return chq, *sorted([first, second]), texts

    def test_option_a_supersedes_the_second_decision(self):  # I7
        chq, winner, loser, texts = self.losing()
        out = self.answer(chq, "Rige lo que decidió la primera.", "A")
        self.assertIn(chq, out["closed"])
        self.assertEqual(out["superseded"], [loser])
        row = self.gaps()[loser]
        self.assertEqual((row["status"].strip("`"), row["closure_reason"]), ("CLOSED", "superseded"))
        self.assertIn(winner, row["resolution_note"])
        self.assertIn(chq, row["resolution_note"])
        ids = [d["id"] for d in closed_decisions(PID, CID)]
        self.assertIn(winner, ids)
        self.assertNotIn(loser, ids)
        forget_read_snapshots()
        decisions = _read(json.loads(run_ok(["export", PID, "--artifact", "decisiones", "--change", CID]))["path"])
        self.assertNotIn(f"### {loser}", decisions)
        self.assertIn(f"### {winner}", decisions)
        self.assertIn("Decisiones reemplazadas", decisions)
        self.assertIn(f"- {loser}: reemplazada por {winner}", decisions)
        brief = _read(json.loads(run_ok(["brief", PID, "--change", CID]))["path"])
        self.assertNotIn(texts[loser], brief)
        self.assertIn(texts[winner], brief)
        self.assertIn("Decisiones reemplazadas", brief)
        exported = _read(json.loads(run_ok(["export", PID, "--artifact", "brief", "--change", CID]))["path"])
        self.assertNotIn(texts[loser], exported)
        self.assertIn(f"Decisión reemplazada: {loser}", exported)

    def test_option_b_supersedes_the_first_decision(self):  # I7
        chq, winner, loser, _texts = self.losing()
        out = self.answer(chq, "Rige lo que decidió la segunda.", "B")
        self.assertEqual(out["superseded"], [winner])
        self.assertEqual(self.gaps()[winner]["closure_reason"], "superseded")
        self.assertNotEqual(self.gaps()[loser].get("closure_reason"), "superseded")

    def test_chq_without_a_valid_option_does_not_close(self):  # I7
        chq, _winner, _loser, _texts = self.losing()
        lines = [f"### {chq}", "- Respuesta: Rige lo que decidió la jefa.", "- Owner / fuente: Jefa de Compras",
                 f"- Evidencia o referencia: {self.ids()['pedido']}:31", "- Estado de decisión: confirmado", ""]
        path = Path.cwd() / "chq-no-option.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        forget_read_snapshots()
        out = json.loads(run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID]))
        self.assertNotIn(chq, out["closed"])
        self.assertEqual(self.gaps()[chq]["status"].strip("`"), "ANSWERED")
        self.assertNotIn("superseded", out)

    def test_contradiction_letters_are_not_compared(self):  # M1
        a = {"id": "GAP-CON-AAAA0001", "option": "A", "elements": ["RN-02"], "citations": []}
        b = {"id": "GAP-CON-BBBB0002", "option": "B", "elements": ["RN-02"], "citations": []}
        self.assertEqual(conflicting_pairs([a, b]), [])


_silence(ClashResolution, {n for n in dir(ClashResolution) if n.startswith("test_") and n in ClashResolution.__dict__})


class EscalationGrowth(escalation_tests.EscalationDecision):
    def test_keep_single_does_not_cover_growth(self):  # I4
        self.setup_border(processes(2))
        run_ok(["sources", "BORR", "--change", ECID, "--keep-single", "--reason", "el release sale junto"])
        self.assertEqual([w["trigger"] for w in escalation_warnings("BORR", ECID)], ["kept_single"])
        self.setup_border(processes(6))
        found = escalation_warnings("BORR", ECID)
        self.assertEqual([w["trigger"] for w in found], ["several_processes"])
        self.assertFalse(found[0].get("decided"))

    def test_keep_single_again_covers_the_new_size(self):  # I4
        self.setup_border(processes(2))
        run_ok(["sources", "BORR", "--change", ECID, "--keep-single", "--reason", "uno"])
        self.setup_border(processes(6))
        run_ok(["sources", "BORR", "--change", ECID, "--keep-single", "--reason", "dos"])
        self.assertEqual([w["trigger"] for w in escalation_warnings("BORR", ECID)], ["kept_single"])

    def test_keep_single_with_no_baseline_is_refused(self):  # M7
        self.setup_border(processes(2))
        code, out = run_refused(["sources", "BORR", "--change", ECID, "--no-baseline", "--keep-single", "--reason", "x"])
        self.assertNotEqual(code, 0)
        self.assertIn("--keep-single", out)


_silence(EscalationGrowth, {n for n in dir(EscalationGrowth) if n.startswith("test_") and n in EscalationGrowth.__dict__})


class ToConfirmTail(speculative_tests.Speculative):
    def statement(self) -> dict:
        return {"text": "Cuando un alta lleva más de 5 días hábiles pendiente, el sistema debe notificar a la gerencia de Compras.",
                "pattern": "event-driven", "delta": "ADDED", "affects": [], "surfaces": []}

    def test_tail_follows_the_request_both_ways(self):  # P2
        first = reconcile_extraction_ears(PID_S, CID_S, "RN-05", [self.statement()], "pedido.md:1")
        (row,) = load_change_ears(PID_S, CID_S)
        self.assertNotIn("a_confirmar", row)
        again = reconcile_extraction_ears(PID_S, CID_S, "RN-05", [self.statement()], "pedido.md:1", a_confirmar=True)
        self.assertEqual(again["added"], [])
        self.assertEqual(again["delta_updated"], first["added"])
        (row,) = load_change_ears(PID_S, CID_S)
        self.assertIs(row["a_confirmar"], True)
        self.assertEqual(row["id"], first["added"][0])
        reconcile_extraction_ears(PID_S, CID_S, "RN-05", [self.statement()], "pedido.md:1", a_confirmar=False)
        (row,) = load_change_ears(PID_S, CID_S)
        self.assertNotIn("a_confirmar", row)
        self.assertFalse(row["source"].endswith("a_confirmar`"))


_silence(ToConfirmTail, {n for n in dir(ToConfirmTail) if n.startswith("test_") and n in ToConfirmTail.__dict__})


class BorderWithToConfirm(review_tests.ReviewCase):
    def test_border_review_keeps_the_rows_left_to_confirm(self):  # P3
        self.confirm_requirement()
        (row,) = load_change_ears(PID, CID)
        import re

        element = re.search(r"EXT:([^`]+)`", row["source"]).group(1)
        reconcile_extraction_ears(PID, CID, element, [{
            "text": row["statement"], "pattern": row["pattern"], "delta": row["delta"], "affects": row["affects"],
            "surfaces": row["surfaces"]}], "pedido", a_confirmar=True)
        forget_read_snapshots()
        text = _read(json.loads(run_ok(["export", PID, "--artifact", "borde", "--change", CID]))["path"])
        bandeja = self.section(text, "### Bandeja de aprobaciones — pantalla")
        self.assertIn(row["statement"], bandeja)
        self.assertIn(f"{row['id']}: {row['statement']} — a confirmar", bandeja)


_silence(BorderWithToConfirm, {n for n in dir(BorderWithToConfirm) if n.startswith("test_") and n in BorderWithToConfirm.__dict__})


if __name__ == "__main__":
    unittest.main()
