"""IMP-414 (H27 inc 5a) task 1: one winner per GAP-CHQ, and a clash that no longer exists retires (inc 4 M2)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
from test_h26_cross_record import CID, PID, CrossCase  # noqa: E402
from test_h27_decision_conflicts import ClashCase  # noqa: E402

from sentinel.change_assumptions import set_change_assumption_status  # noqa: E402
from sentinel.changes import accept_prior_decision, change_gaps_path  # noqa: E402
from sentinel.core.io import forget_read_snapshots, read_json  # noqa: E402
from sentinel.crosses.record import _save_change_gaps, record_cross  # noqa: E402
from sentinel.decision_conflicts import superseded_path  # noqa: E402
from sentinel.decision_memory import closed_decisions, superseded_decisions  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.prior_decisions import load_priors, prior_note, save_priors  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

QUOTE = "quiero consultar quién aprobó cada alta y cuándo"


class Flip(ClashCase):
    def stored(self) -> dict:
        return read_json(superseded_path(workspace_path(PID), CID), {})["decisions"]

    def test_flip_restores_earlier_loser(self):
        first, second, r = self.clash()
        chq = r["decision_conflicts"][0]
        before = self.gaps()[second]["closure_reason"]
        self.answer(chq, "Rige la primera.", "A")
        self.assertEqual([d["id"] for d in superseded_decisions(PID, CID)], [second])
        self.assertEqual(self.stored()[second]["by"], chq)
        result = self.answer(chq, "Rige la segunda.", "B")
        self.assertEqual(result["restored"], [second])
        row = self.gaps()[second]
        self.assertEqual(row["status"].strip("`"), "CLOSED")
        self.assertEqual(row["closure_reason"], before)
        self.assertEqual(self.gaps()[first]["resolution_note"], f"reemplazada por {second} según {chq}")
        self.assertEqual([d["id"] for d in superseded_decisions(PID, CID)], [first])

    def test_same_answer_twice_keeps_one_winner(self):
        first, second, r = self.clash()
        chq = r["decision_conflicts"][0]
        self.answer(chq, "Rige la primera.", "A")
        self.answer(chq, "Rige la primera.", "A")
        self.assertEqual([d["id"] for d in superseded_decisions(PID, CID)], [second])
        self.assertEqual(list(self.stored()), [second])

    def test_reagreeing_retires_open_conflict(self):
        first, second, r = self.clash()
        chq = r["decision_conflicts"][0]
        before = self.blocking()
        out = self.answer(second, "Rige el pedido: el umbral es 5.000.000.", "B")
        self.assertEqual(out["conflicts_retired"], [chq])
        row = self.gaps()[chq]
        self.assertEqual(row["status"].strip("`"), "CLOSED")
        self.assertEqual(row["closure_reason"].strip("`"), "retired")
        self.assertEqual(row["resolution_note"], f"choque retirado: {first} y {second} ya no chocan")
        self.assertNotIn(chq, [d["id"] for d in closed_decisions(PID, CID)])
        self.assertEqual(self.blocking(), before - 1)


class ValidateSpy(CrossCase):
    def test_validate_refreshes(self):
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        forget_read_snapshots()
        srd = next(i for i in self.gaps() if i.startswith("GAP-SRD-"))
        item = {"id": "ASM-HIST", "lens": "design",
                "statement": "El historial del auditor se muestra como una pestaña del detalle del alta.",
                "owner": "BA de Compras", "risk": "med", "justification": QUOTE,
                "closes_gap": srd, "validate_with": "Diseño"}
        path = Path.cwd() / "asm-followup.json"
        path.write_text(json.dumps({"assumptions": [item]}, ensure_ascii=False), encoding="utf-8")
        run_ok(["assume", PID, "--change", CID, "--source", str(path)])
        forget_read_snapshots()
        with mock.patch("sentinel.decision_conflicts.refresh_decision_conflicts",
                        return_value={"opened": [], "retired": []}) as spy:
            set_change_assumption_status(PID, CID, "ASM-HIST", "validate", "Diseño lo confirmó")
        spy.assert_called_with(PID, CID)


class AcceptSpy(CrossCase):
    def test_accept_prior_refreshes(self):
        patcher = mock.patch("sentinel.prior_decisions.live_prior_answer",
                             side_effect=lambda _p, _c, entry, live=None: entry.get("answer"))
        patcher.start()
        self.addCleanup(patcher.stop)
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        forget_read_snapshots()
        base = workspace_path(PID)
        srd = next(i for i in self.gaps() if i.startswith("GAP-SRD-"))
        entry = {"match": "linked", "prior": "GAP-DIS-0A1B2C3D", "basis": "quote", "answer": "Rige el pedido.",
                 "option": "", "score": 1.0, "at": "2026-11-24T00:00:00+00:00"}
        priors = load_priors(base, CID)
        priors[srd] = entry
        save_priors(base, CID, priors)
        path = change_gaps_path(base, CID)
        rows = [g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g.get("id") != "NONE"]
        for row in rows:
            if row["id"] == srd:
                row["status"] = "PRE_DECIDED"
                row["resolution_note"] = prior_note(entry, "es")
        _save_change_gaps(PID, CID, path, rows)
        forget_read_snapshots()
        with mock.patch("sentinel.decision_conflicts.refresh_decision_conflicts",
                        return_value={"opened": [], "retired": []}) as spy:
            accept_prior_decision(PID, CID, srd)
        spy.assert_called_with(PID, CID)


if __name__ == "__main__":
    unittest.main()
