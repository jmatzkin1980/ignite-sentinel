"""IMP-412 (H27 inc 4) task 1: `/assume --change` closes the question of a change as an assumption, with a life cycle."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
from test_h26_cross_record import CID, PID, CrossCase  # noqa: E402
from test_mcp_parity import _tools  # noqa: E402

from sentinel.assumptions import load_assumptions  # noqa: E402
from sentinel.changes import get_change  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots, read_json  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.decision_memory import closed_decisions  # noqa: E402
from sentinel.gaps import count_gaps  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

QUOTE = "quiero consultar quién aprobó cada alta y cuándo"


def run_err(argv: list[str]) -> tuple[int, str]:
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


class ChangeAssumptions(CrossCase):
    def setUp(self):
        super().setUp()
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        forget_read_snapshots()
        self.srd = next(i for i in self.gaps() if i.startswith("GAP-SRD-"))

    def asm_json(self, **over) -> Path:
        item = {"id": "ASM-HIST", "lens": "design",
                "statement": "El historial del auditor se muestra como una pestaña del detalle del alta.",
                "owner": "BA de Compras", "risk": "med", "justification": QUOTE,
                "closes_gap": self.srd, "validate_with": "Diseño"}
        item.update(over)
        path = Path.cwd() / f"asm-{len(list(Path.cwd().glob('asm-*')))}.json"
        path.write_text(json.dumps({"assumptions": [item]}, ensure_ascii=False), encoding="utf-8")
        return path

    def register(self) -> dict:
        return json.loads(run_ok(["assume", PID, "--change", CID, "--source", str(self.asm_json())]))

    def base(self) -> Path:
        return workspace_path(PID)

    def register_rows(self) -> list[dict]:
        return load_assumptions(PID, self.base() / "01_discovery" / CID / "assumptions.md")

    def test_assume_closes_change_gap(self):
        out = self.register()
        self.assertEqual(out["accepted"], ["ASM-HIST"])
        self.assertEqual(out["closed_gaps"], [self.srd])
        row = self.gaps()[self.srd]
        self.assertEqual(row["status"].strip("`"), "CLOSED")
        self.assertEqual(row["closure_reason"], "assumed")
        self.assertEqual(row["resolution_note"], "supuesto ASM-HIST: a validar con Diseño")
        self.assertEqual(get_change(PID, CID)["gap_counts"]["assumed"], 1)
        text = (self.base() / "01_discovery" / CID / "assumptions.md").read_text(encoding="utf-8")
        self.assertIn("| ASM-HIST | design |", text)
        self.assertIn("| ASSUMED |", text)
        self.assertFalse((self.base() / "01_discovery" / "assumptions.md").exists())
        meta = read_json(self.base() / "01_discovery" / CID / "assumptions.json", {})["assumptions"]["ASM-HIST"]
        self.assertEqual({k: meta[k] for k in ("validate_with", "gap", "origin")},
                         {"validate_with": "Diseño", "gap": self.srd, "origin": "assume"})
        self.assertEqual((meta["reason"], meta["decided_at"]), ("", ""))
        self.assertEqual(load_assumptions(PID), [])

    def test_bad_gap_refused_without_writing(self):
        code, err = run_err(["assume", PID, "--change", CID, "--source", str(self.asm_json(closes_gap="GAP-NOPE"))])
        self.assertEqual(code, 3)
        self.assertIn(f"GAP-NOPE no es una pregunta de {CID}", err)
        self.assertFalse((self.base() / "01_discovery" / CID / "assumptions.md").exists())
        self.register()
        code, err = run_err(["assume", PID, "--change", CID, "--source", str(self.asm_json(id="ASM-OTRO"))])
        self.assertEqual(code, 3)
        self.assertIn("ya está cerrada; un supuesto no reemplaza una decisión", err)

    def test_quote_must_be_local(self):
        code, err = run_err(["assume", PID, "--change", CID, "--source",
                             str(self.asm_json(justification="una frase que no está en ninguna fuente local"))])
        self.assertEqual(code, 3)
        self.assertIn("not found verbatim", err)

    def test_unknown_change_refused(self):
        # get_change refuses an unknown change as a gate (4), like every other --change command
        code, err = run_err(["assume", PID, "--change", "CHG-009", "--source", str(self.asm_json())])
        self.assertNotEqual(code, 0)
        self.assertIn("CHG-009 no es un cambio abierto", err)
        self.assertFalse((self.base() / "01_discovery" / "CHG-009").exists())

    def test_invalidate_reopens(self):
        self.register()
        out = json.loads(run_ok(["assume", PID, "--change", CID, "--id", "ASM-HIST", "--invalidate",
                                 "--reason", "Diseño no tiene pestañas"]))
        self.assertEqual(out["gap_status"], "OPEN")
        row = self.gaps()[self.srd]
        self.assertTrue(row["resolution_note"].startswith(
            "reopened: ASM-HIST invalidated; previous closure kept: assumed: supuesto ASM-HIST"))
        self.assertEqual(self.register_rows()[0]["status"], "INVALIDATED")
        self.assertNotIn("assumed", out["gap_counts"])
        meta = read_json(self.base() / "01_discovery" / CID / "assumptions.json", {})["assumptions"]["ASM-HIST"]
        self.assertEqual(meta["reason"], "Diseño no tiene pestañas")
        self.assertTrue(meta["decided_at"])

    def test_validate_keeps_closed(self):
        self.register()
        run_ok(["assume", PID, "--change", CID, "--id", "ASM-HIST", "--validate",
                "--reason", "Diseño lo confirmó en la revisión"])
        row = self.gaps()[self.srd]
        self.assertEqual(row["status"].strip("`"), "CLOSED")
        self.assertEqual(row["closure_reason"], "answered")
        self.assertEqual(row["resolution_note"], "supuesto ASM-HIST validado: Diseño lo confirmó en la revisión")
        self.assertEqual(self.register_rows()[0]["status"], "VALIDATED")
        code, err = run_err(["assume", PID, "--change", CID, "--id", "ASM-HIST", "--validate", "--reason", "otra vez"])
        self.assertEqual(code, 3)
        self.assertIn("ya está VALIDATED", err)

    def test_reason_and_guards(self):
        self.register()
        code, err = run_err(["assume", PID, "--change", CID, "--id", "ASM-HIST", "--invalidate"])
        self.assertEqual(code, 3)
        self.assertIn("necesita --reason", err)
        code, err = run_err(["assume", PID])
        self.assertEqual(code, 3)
        self.assertIn("/assume needs --source PATH", err)
        code, _ = run_err(["assume", PID, "--id", "ASM-HIST", "--validate"])
        self.assertNotEqual(code, 0)
        code, err = run_err(["assume", PID, "--change", CID, "--id", "ASM-HIST", "--reason", "x"])
        self.assertEqual(code, 3)
        self.assertIn("/assume --change takes", err)
        code, _ = run_err(["assume", PID, "--change", CID, "--id", "ASM-NOPE", "--validate", "--reason", "x"])
        self.assertEqual(code, 3)

    def test_count_gaps_assumed(self):
        self.assertEqual(
            count_gaps([{"id": "G", "severity": "high", "status": "CLOSED", "closure_reason": "assumed"}]),
            {"open": 0, "answered": 0, "partially_closed": 0, "closed": 1, "blocking_open": 0, "total": 1, "assumed": 1})
        self.assertNotIn("assumed", count_gaps([]))

    def test_assumption_is_not_a_decision(self):
        self.register()
        self.assertNotIn(self.srd, [d["id"] for d in closed_decisions(PID, CID)])

    def test_mcp_assume_change(self):
        out = _tools()["sentinel_assume"](project_id=PID, change=CID, source=str(self.asm_json()))
        self.assertEqual(out["exit_code"], 0, out)
        self.assertEqual(out["output"]["action"], "assume")


if __name__ == "__main__":
    unittest.main()
