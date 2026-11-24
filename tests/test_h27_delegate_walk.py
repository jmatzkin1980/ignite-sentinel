"""IMP-412 (H27 inc 4) task 8: the BA delegates and reviews, end to end through the CLI.

The design cross-read opens a divergence and a design-only question. One answer file confirms the divergence on the
BA's behalf and records the other question as an assumption to validate with Design. The BA then gets the review
exports, and invalidates the assumption: the question opens again and the assumption warning disappears.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
from test_h26_cross_record import CID, PID, CrossCase  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402

QUOTE = "quiero consultar quién aprobó cada alta y cuándo"
STATEMENT = "El historial del auditor se muestra como una pestaña del detalle del alta."


def _read(path: str) -> str:
    found = Path(path)
    return (found if found.is_absolute() else Path.cwd() / found).read_text(encoding="utf-8")


class DelegateAndReview(CrossCase):
    def test_the_ba_delegates_and_reviews(self):
        run_ok(["cross", PID, "--change", CID, "--kind", "diseno", "--claims", str(self.write("cruce_diseno.md"))])
        forget_read_snapshots()
        dis = next(i for i in self.gaps() if i.startswith("GAP-DIS-"))
        srd = next(i for i in self.gaps() if i.startswith("GAP-SRD-"))
        asm = "ASM-" + srd[4:]

        answers = Path.cwd() / "respuestas.md"
        answers.write_text("\n".join([
            f"### {dis}", "- Respuesta: Rige el pedido del área de Compras.", "- Opción: B",
            "- Owner / fuente: Jefa de Compras", f"- Evidencia o referencia: {self.ids()['pedido']}:1",
            "- Estado de decisión: confirmado", "- Confirmado por: delegación del BA", "",
            f"### {srd}", f"- Respuesta: {STATEMENT}", "- Owner / fuente: BA de Compras",
            f'- Evidencia o referencia: "{QUOTE}"', "- Estado de decisión: supuesto", "- Valida: Diseño", "",
        ]) + "\n", encoding="utf-8")
        out = json.loads(run_ok(["resolve-gaps", PID, "--source", str(answers), "--change", CID]))
        self.assertIn(dis, out["closed"])
        self.assertEqual(out["assumed"], [srd])
        self.assertEqual(out["assumptions"], [asm])
        self.assertEqual(out["delegated"], [dis])

        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertEqual(status["assumptions"]["open"], 1)
        self.assertEqual(status["delegated"]["total"], 1)
        self.assertIn(f"1 supuesto(s) a validar: {asm}", status["verdict"]["warnings"])

        border = json.loads(run_ok(["export", PID, "--artifact", "borde", "--change", CID]))
        self.assertTrue(Path(border["path"]).is_file())
        decisions = json.loads(run_ok(["export", PID, "--artifact", "decisiones", "--change", CID]))
        text = _read(decisions["path"])
        self.assertIn("confirmado por delegación del BA", text)
        self.assertIn("## Supuestos (no son decisiones: a validar)", text)
        self.assertNotIn(f"### {srd}", text)
        view = json.loads(run_ok(["view", PID, "--artifact", "decisiones", "--change", CID]))
        self.assertTrue(Path(view["path"]).is_file())

        run_ok(["assume", PID, "--change", CID, "--id", asm, "--invalidate", "--reason", "Diseño no lo acepta"])
        forget_read_snapshots()
        self.assertEqual(self.gaps()[srd]["status"].strip("`"), "OPEN")
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertFalse(any("supuesto" in warning for warning in status["verdict"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
