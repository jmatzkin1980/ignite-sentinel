"""IMP-414 (H27 inc 5a) task 4: the body of the final change export is the consolidated text."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, run_ok  # noqa: E402
import test_h27_consolidation  # noqa: E402
from test_h26_cross_record import CID, CROSSES, PID  # noqa: E402

from sentinel.brief_integrity import RESIDUE_PATTERNS  # noqa: E402
from sentinel.brief_schema import load_brief_schema  # noqa: E402
from sentinel.compilers.change_deliverable import render_change_deliverable, request_follows_v2, v2_heading_place  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.extraction.inventory import element_lines, parse_request_elements  # noqa: E402

CONSOLIDATED = "mayor a 1.000.000 requiere aprobación de la jefa de Compras"
ORIGINAL = "mayor a 5.000.000 requiere aprobación de la jefa de Compras"
ANSWER = test_h27_consolidation.ANSWER


def place(text: str, sid: str) -> str:
    """The text of one numbered subsection of the v2 brief, up to the next `##` or `###` heading."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"### {sid} "))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith(("## ", "### "))), len(lines))
    return "\n".join(lines[start:end])


def body_of(text: str) -> str:
    return text.split("## A.", 1)[0]


class FinalCase(test_h27_consolidation.ConsolidationCase):
    request = "pedido_contradiccion.md"

    def apply(self, **over) -> None:
        """Record the replacement of RN-02 and confirm it (the BA's one-by-one step)."""
        result = self.submit_text(self.rep(**over))
        self.assertEqual(result["recorded"], ["RN-02"], result)
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])

    def propose(self, block: str, *elements: str) -> None:
        path = Path.cwd() / "final-prop.md"
        path.write_text(block, encoding="utf-8")
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--proposals", str(path)])
        for element in elements:
            forget_read_snapshots()
            run_ok(["extract", PID, "--change", CID, "--confirm-item", element])

    def lines_of(self, element_id: str) -> str:
        text = (CROSSES / self.request).read_text(encoding="utf-8")
        found = {e["id"]: e for e in parse_request_elements(text, "F-01", "pedido.md")}
        first, last = element_lines(found[element_id])
        return f"{first}-{last}"

    def final(self) -> str:
        forget_read_snapshots()
        return render_change_deliverable(PID, CID, True)

    def working(self) -> str:
        forget_read_snapshots()
        return render_change_deliverable(PID, CID, False)


class Consolidated(FinalCase):
    def test_replacement_applied_with_ref(self):
        self.apply()
        text = self.final()
        line = next(line for line in text.splitlines() if "RN-02 — texto consolidado (" in line)
        self.assertIn(self.dis, line)
        self.assertIn("[modificado]", line)
        self.assertIn(CONSOLIDATED, text)
        self.assertNotIn(ORIGINAL, text)
        self.assertNotIn("antes decía", text)
        self.assertNotIn("~~", text)
        self.assertEqual([p.pattern for p in RESIDUE_PATTERNS if p.search(text)], [])

    def test_ears_out_of_final_body(self):
        self.apply()
        final = self.final()
        self.assertNotIn("REQ-EARS-", final)
        working = self.working()
        self.assertIn("REQ-EARS-", working)
        self.assertIn("Fuera de este cambio: RN-06", working)

    def test_requirement_transcribed(self):
        self.apply()
        self.propose("\n".join([
            "### RN-01", "- Tratamiento: requisito", f"- Líneas: {self.lines_of('RN-01')}",
            '- Cita: "El CUIT del proveedor debe ser único"',
            "- Enunciado: Cuando el analista envía un alta con un CUIT ya registrado, el sistema debe rechazarla.",
            "  - Delta: ADDED", "  - Superficie: Aprobación por monto", ""]), "RN-01")
        text = self.final()
        self.assertIn("[nuevo] RN-01 — texto literal del pedido (", text)
        self.assertIn("El CUIT del proveedor debe ser único", text)

    def test_discard_only_in_scope(self):
        self.apply()
        text = self.final()
        self.assertIn("No entra: RN-06 — Los proveedores del exterior quedan fuera de este cambio.", place(text, "6.2"))
        self.assertEqual(body_of(text).count("proveedores del exterior quedan fuera"), 1)
        self.assertNotIn("Fuera de este cambio: RN-06", text)

    def test_decision_answers_leave_body(self):
        self.apply()
        self.assertNotIn(ANSWER, body_of(self.final()))
        self.assertIn(ANSWER, body_of(self.working()))

    def test_related_subsection(self):
        self.apply(**{"Ubicación": "3.6"})
        text = self.final()
        self.assertIn("#### Relacionado con RN-02 (", place(text, "3.6").replace("\n####", "\n#####x") if False else text)
        lines = text.splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("### 3.6 "))
        end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith(("## ", "### ")))
        inside = "\n".join(lines[start:end])
        self.assertIn("#### Relacionado con RN-02 (", inside)
        self.assertIn(CONSOLIDATED, inside)
        self.assertNotIn("RN-02 — texto consolidado", place(text, "2.2"))

    def test_english_change(self):
        from test_h26_cross_record import set_language

        set_language(PID, "en")
        forget_read_snapshots()
        self.apply(**{"Ubicación": "3.6"})
        text = self.final()
        self.assertIn("RN-02 — consolidated text (", text)
        self.assertIn("#### Related to RN-02 (", text)
        self.assertIn("Not included: RN-06", text)


class V2Pure(unittest.TestCase):
    def test_follows_v2(self):
        def of(*headings: str) -> list[dict]:
            return [{"id": f"E-{i}", "section": h} for i, h in enumerate(headings)]

        self.assertTrue(request_follows_v2(of("2.2 Reglas de Negocio Críticas", "Proceso To-Be",
                                              "Criterios de Aceptación del Release")))
        self.assertFalse(request_follows_v2(of("Reglas de negocio", "Proceso")))
        self.assertFalse(request_follows_v2(of("2.2 Reglas de Negocio Críticas", "3.2 Proceso To-Be")))
        self.assertEqual(v2_heading_place("Manejo de Errores / Casos Borde", load_brief_schema()), "3.6")
        self.assertEqual(v2_heading_place("2.2 Lo que sea", load_brief_schema()), "2.2")
        self.assertEqual(v2_heading_place("9.9 Nada", load_brief_schema()), "")
        self.assertEqual(v2_heading_place("", load_brief_schema()), "")


class V2Request(FinalCase):
    request = "pedido_v2.md"

    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(CROSSES / "pedido_v2.md", root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(CROSSES / "prototipo-aprobaciones.html"),
                "--role", "diseno_nuevo", "--change", CID])

    def test_v2_structure_kept(self):
        text = (CROSSES / "pedido_v2.md").read_text(encoding="utf-8")
        found = parse_request_elements(text, "F-01", "pedido.md")
        self.assertTrue(request_follows_v2(found))
        process = next(e for e in found if e["id"].startswith("SEC-") and "proceso" in e["id"])
        first, last = element_lines(process)
        self.apply()
        self.propose("\n".join([
            f"### {process['id']}", "- Tratamiento: seccion", f"- Líneas: {first}-{last}", "- Seccion: proceso",
            "- Texto: El analista completa los datos fiscales, bancarios y de contacto del proveedor.",
            '- Cita: "El analista completa los datos fiscales"', ""]), process["id"])
        final = self.final()
        self.assertIn("El analista completa los datos fiscales", place(final, "3.2"))
        self.assertIn(CONSOLIDATED, place(final, "2.2"))
        self.assertNotIn(CONSOLIDATED, place(final, "3.2"))


if __name__ == "__main__":
    unittest.main()
