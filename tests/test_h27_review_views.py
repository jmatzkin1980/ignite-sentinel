"""IMP-412 (H27 inc 4) task 6: review views of a change for third parties (borde, decisiones) and the change's FAQ."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok, waive_crosses  # noqa: E402
from test_h26_cross_record import CID, CROSSES, PID, CrossCase, set_language  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURE = CROSSES / "coherencia_pantalla_sin_endpoint.json"
EARS = "Cuando la jefa abre la bandeja, el sistema debe listar las altas pendientes de aprobación."
QUOTE = "quiero consultar quién aprobó cada alta y cuándo"
DIS_ANSWER = "Rige el pedido: el umbral es 5.000.000 y el prototipo se corrige."


def run_err(argv: list[str]) -> tuple[int, str]:
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


class ReviewCase(CrossCase):
    def exported(self, artifact: str, *extra: str) -> tuple[dict, str]:
        out = json.loads(run_ok(["export", PID, "--artifact", artifact, "--change", CID, *extra]))
        return out, Path(out["path"]).read_text(encoding="utf-8")

    def respond(self, text: str) -> None:
        path = Path.cwd() / f"resp-{len(list(Path.cwd().glob('resp-*')))}.md"
        path.write_text(text, encoding="utf-8")
        forget_read_snapshots()
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])

    def close_dis(self) -> str:
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        dis = next(g for g in result["gaps"] if g.startswith("GAP-DIS-"))
        self.respond("\n".join([
            f"### {dis}", f"- Respuesta: {DIS_ANSWER}", "- Opción: B", "- Owner / fuente: Jefa de Compras",
            f"- Evidencia o referencia: {self.ids()['pedido']}:31", "- Estado de decisión: confirmado", ""]))
        return dis

    def confirm_requirement(self) -> None:
        """One confirmed EARS row on the screen of the border (the extraction proposes it, the BA confirms)."""
        import tempfile

        from sentinel.extraction.confirm import confirm_proposals
        from sentinel.extraction.inventory import build_inventory, element_lines, element_text, load_inventory
        from sentinel.extraction.proposals import record_proposals

        waive_crosses(PID, CID, coherence=False)
        build_inventory(PID, CID)
        base = workspace_path(PID)
        element = next(e for e in (load_inventory(base, CID) or {}).get("elements", [])
                       if "bandeja" in (element_text(base, e) or "").lower())
        quote = " ".join((element_text(base, element) or "").split())[:60].strip()
        first, last = element_lines(element)
        block = "\n".join([f"### {element['id']}", "- Tratamiento: requisito", f"- Líneas: {first}-{last}",
                           f'- Cita: "{quote}"', f"- Enunciado: {EARS}", "  - Delta: ADDED",
                           "  - Superficie: Bandeja de aprobaciones", ""])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "proposals.md"
            path.write_text(block, encoding="utf-8")
            result = record_proposals(PID, CID, path)
        self.assertFalse(result.get("rejected"), result)
        confirm_proposals(PID, CID, "all")
        forget_read_snapshots()

    def section(self, text: str, heading: str) -> str:
        body = text.split(heading, 1)[1]
        return body.split("\n## ", 1)[0] if heading.startswith("## ") else body.split("\n### ", 1)[0].split("\n## ", 1)[0]


class BorderReview(ReviewCase):
    def test_border_review(self):
        self.confirm_requirement()
        run_ok(["self-review", PID, "--crosses", "--change", CID, "--source", str(FIXTURE)])
        out, text = self.exported("borde")
        self.assertEqual(out["deliverable"], "working")
        self.assertTrue(out["path"].endswith("08_context_packs/exports/CHG-001-borde.md"))
        self.assertIn("# Borde explicado — CHG-001", text)
        self.assertIn("Respuesta del BA (GAP-SCOPE): El alta de proveedores con aprobación por monto.", text)
        self.assertNotIn("BORRADOR", text)
        for zone in ("## Nuevo (se construye)", "## Adyacente (existe y se toca)", "## Preservado (no cambia)"):
            self.assertIn(zone, text)
        bandeja = self.section(text, "### Bandeja de aprobaciones — pantalla")
        self.assertIn(EARS, bandeja)
        self.assertRegex(bandeja, r"GAP-XRV-[0-9A-F]+: ¿Qué endpoint alimenta la bandeja de aprobaciones\?")
        self.assertIn("- Dudas abiertas: ninguna", self.section(text, "### Validación de CUIT — regla"))
        alta = self.section(text, "### Alta de proveedores — endpoint")
        self.assertIn("«Que el alta de proveedores de Compras deje de depender de firmas en papel", alta)
        self.assertIn("F-", alta.split("- De dónde sale:")[1])
        self.assertIn("sin descripción registrada", self.section(text, "### Aprobación por monto — regla"))
        self.assertIn("sin filas de no regresión todavía", self.section(text, "### Validación de CUIT — regla").replace(
            "(sin filas de no regresión todavía)", "sin filas de no regresión todavía"))
        self.assertIn("## Superficies nuevas decididas\n\nninguna", text)
        again = Path(out["path"]).read_text(encoding="utf-8")
        self.assertEqual(again, text)
        review = workspace_path(PID) / "02_requirements" / CID / "review" / "borde.md"
        self.assertEqual(review.read_text(encoding="utf-8"), text)

    def test_new_surfaces_section(self):
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        sed = next(g for g in result["gaps"] if g.startswith("GAP-SED-"))
        forget_read_snapshots()
        run_ok(["cross", PID, "--change", CID, "--accept-new", sed, "--type", "pantalla",
                "--name", "Delegación de aprobaciones"])
        _out, text = self.exported("borde")
        self.assertIn("## Superficies nuevas decididas", text)
        self.assertIn(f"Delegación de aprobaciones (pantalla) — aceptada ({sed})", text)

    def test_english_labels(self):
        set_language(PID, "en")
        _out, text = self.exported("borde")
        self.assertIn("# Border explained — CHG-001", text)
        self.assertIn("- What it is:", text)
        self.assertIn("- Open doubts: none", text)


class DecisionsReview(ReviewCase):
    def register_assumption(self) -> tuple[str, str]:
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        srd = next(g for g in result["gaps"] if g.startswith("GAP-SRD-"))
        item = {"id": "ASM-HIST", "lens": "design",
                "statement": "El historial del auditor se muestra como una pestaña del detalle del alta.",
                "owner": "BA de Compras", "risk": "med", "justification": QUOTE,
                "closes_gap": srd, "validate_with": "Diseño"}
        path = Path.cwd() / "asm-0.json"
        path.write_text(json.dumps({"assumptions": [item]}, ensure_ascii=False), encoding="utf-8")
        forget_read_snapshots()
        run_ok(["assume", PID, "--change", CID, "--source", str(path)])
        return "ASM-HIST", srd

    def test_decisions_review(self):
        dis = self.close_dis()
        asm, srd = self.register_assumption()
        _out, text = self.exported("decisiones")
        self.assertIn("# Decisiones del cambio — CHG-001", text)
        design = self.section(text, "## Diseño")
        self.assertIn(f"### {dis} — ", design)
        self.assertIn("- Opción elegida: B", design)
        self.assertIn(f"- Respuesta: {DIS_ANSWER}", design)
        self.assertIn("- Decidió: Jefa de Compras", design)
        self.assertIn("### GAP-SCOPE — ", self.section(text, "## Producto"))
        self.assertIn("## Supuestos (no son decisiones: a validar)", text)
        self.assertIn(f"{asm}: El historial del auditor se muestra como una pestaña del detalle del alta. "
                      f"— a validar con Diseño ({srd})", text.split("## Supuestos")[1])
        self.assertNotIn(f"### {srd}", text)

    def test_english_labels(self):
        self.close_dis()
        set_language(PID, "en")
        _out, text = self.exported("decisiones")
        self.assertIn("# Decisions of the change — CHG-001", text)
        self.assertIn("- Chosen option: B", text)
        self.assertIn("- Decided by: Jefa de Compras", text)

    def test_delegated_and_drafted_marks(self):
        from sentinel.delegation import delegations_path

        dis = self.close_dis()
        path = delegations_path(workspace_path(PID), CID)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": 1, "change_id": CID,
                                    "gaps": {dis: {"at": "x", "note": "delegado", "response": "r"}}}), encoding="utf-8")
        forget_read_snapshots()
        _out, text = self.exported("decisiones")
        self.assertIn("- Decidió: Jefa de Compras — confirmado por delegación del BA", text)


class FaqAndPlumbing(ReviewCase):
    def test_faq_and_interview_for_change(self):
        self.close_dis()
        out = json.loads(run_ok(["export", PID, "--artifact", "gaps", "--format", "faq", "--change", CID]))
        self.assertTrue(out["path"].endswith("exports/CHG-001-gaps-faq.md"))
        text = Path(out["path"]).read_text(encoding="utf-8")
        self.assertIn(DIS_ANSWER, text)
        out = json.loads(run_ok(["export", PID, "--artifact", "gaps", "--format", "interview", "--change", CID]))
        self.assertTrue(out["path"].endswith("exports/CHG-001-gaps-interview.md"))

    def test_view_review(self):
        self.close_dis()
        out = json.loads(run_ok(["view", PID, "--artifact", "decisiones", "--change", CID]))
        self.assertTrue(out["path"].replace("\\", "/").endswith("08_context_packs/views/CHG-001-decisiones.html"))
        self.assertTrue(Path(out["path"]).is_file())

    def test_review_needs_change(self):
        code, err = run_err(["export", PID, "--artifact", "borde"])
        self.assertEqual(code, 3)
        self.assertIn("goes with --change CHG-NNN", err)
        code, err = run_err(["view", PID, "--artifact", "decisiones"])
        self.assertEqual(code, 3)
        self.assertIn("goes with --change CHG-NNN", err)
        code, _err = run_err(["export", PID, "--artifact", "borde", "--format", "interview", "--change", CID])
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
