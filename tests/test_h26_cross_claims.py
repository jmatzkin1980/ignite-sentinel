"""IMP-404 (H26 inc 4) task 2: the claims file of a cross-read and the check of its quotes by source role."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.crosses import cross_path, crosses_dir, normalize_kind  # noqa: E402
from sentinel.crosses.claims import locate_quote, parse_claims, validate_claims, visible_text  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.status import change_sources  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CROSSES = FIXTURES / "change_crosses"
SAD = FIXTURES / "change_baseline" / "sad-compras.md"
PID = "CRUZ"
CID = "CHG-001"
HTML = (CROSSES / "prototipo-aprobaciones.html").read_text(encoding="utf-8")

EN_TAGS = {
    "[RESPALDADO]": "[BACKED]",
    "[SIN RESPALDO EN DISEÑO]": "[NOT IN DESIGN]",
    "[SOLO EN DISEÑO]": "[ONLY IN DESIGN]",
    "[DIVERGENCIA]": "[DIVERGENCE]",
    "  - Pedido:": "  - Request:",
    "  - Diseño:": "  - Design:",
}


def english(text: str) -> str:
    for spanish, other in EN_TAGS.items():
        text = text.replace(spanish, other)
    return text


def numbered(text: str) -> str:
    return text.replace("F-PED", "F-01").replace("F-DIS", "F-04")


class Parse(unittest.TestCase):
    def test_parse_design_example(self):
        claims, errors = parse_claims(numbered((CROSSES / "cruce_diseno.md").read_text(encoding="utf-8")))
        self.assertEqual(errors, [])
        self.assertEqual([c["tag"] for c in claims],
                         ["respaldado", "respaldado", "sin_respaldo", "solo_en_diseno", "divergencia"])
        first = claims[0]
        self.assertEqual([c["side"] for c in first["citations"]], ["pedido", "diseno"])
        self.assertEqual(first["citations"][1]["quote"], "Bandeja de aprobaciones")
        self.assertEqual(first["citations"][0]["source_id"], "F-01")
        self.assertEqual(first["line"], 3)
        self.assertEqual(first["citations"][0]["line"], 4)

    def test_parse_english_tags(self):
        text = english(numbered((CROSSES / "cruce_diseno.md").read_text(encoding="utf-8")))
        claims, errors = parse_claims(text, "en")
        self.assertEqual(errors, [])
        self.assertEqual([c["tag"] for c in claims],
                         ["respaldado", "respaldado", "sin_respaldo", "solo_en_diseno", "divergencia"])
        self.assertEqual([c["side"] for c in claims[0]["citations"]], ["pedido", "diseno"])

    def test_parse_errors(self):
        _, errors = parse_claims('- [RESPALDO] Algo.\n  - Pedido: F-01 "una cita que no cuenta aca"\n')
        self.assertTrue(any(e.startswith("línea 1:") and "etiqueta desconocida" in e for e in errors), errors)
        _, errors = parse_claims('  - Pedido: F-01 "una cita sin afirmacion antes"\n- [RESPALDADO] Algo.\n')
        self.assertTrue(any(e.startswith("línea 1:") and "sin una afirmación" in e for e in errors), errors)
        claims, errors = parse_claims('- [RESPALDADO] Algo.\n  - Pedido: "sin fuente"\n')
        self.assertTrue(any(e.startswith("línea 2:") and "falta F-NN" in e for e in errors), errors)
        self.assertEqual(len(claims), 1)
        _, errors = parse_claims("Solo texto.\nOtra línea.\n")
        self.assertEqual(errors, ["el archivo no trae ninguna afirmación etiquetada"])
        _, errors = parse_claims("- [BACKED] Something.\n  - Request: \"no source id\"\n", "en")
        self.assertTrue(any(e.startswith("line 2:") for e in errors), errors)

    def test_curly_quotes_and_case_insensitive_side(self):
        claims, errors = parse_claims("- [RESPALDADO] Algo.\n  - pedido: F-02 “texto entre comillas curvas”\n")
        self.assertEqual(errors, [])
        self.assertEqual(claims[0]["citations"][0]["quote"], "texto entre comillas curvas")

    def test_kinds(self):
        self.assertEqual(normalize_kind("Diseño", "es"), "diseno")
        self.assertEqual(normalize_kind("BASELINE", "en"), "linea_de_base")
        with self.assertRaises(InputError) as ctx:
            normalize_kind("otro", "es")
        self.assertIn("Tipo de cruce desconocido «otro»", str(ctx.exception))
        base = Path("x")
        self.assertEqual(cross_path(base, CID, "diseno"), crosses_dir(base, CID) / "diseno.json")
        self.assertEqual(crosses_dir(base, CID), base / "01_discovery" / CID / "crosses")

    def test_visible_text_and_locate(self):
        visible = visible_text(HTML, ".html")
        self.assertNotIn("border:1px", visible)
        self.assertNotIn("<h1>", visible)
        self.assertEqual(visible_text("<b>x</b>", ".md"), "<b>x</b>")
        found = locate_quote(HTML, ".html", "Aprobar Rechazar")
        self.assertIsNotNone(found)
        self.assertIsNone(found["line"])
        found = locate_quote(HTML, ".html", "Bandeja de aprobaciones")
        self.assertEqual(found["line"], 7)
        self.assertIsNone(locate_quote(HTML, ".html", "border:1px solid"))

    def test_locate_markdown_line_and_wrapped_quote(self):
        text = "uno\ndos tres\ncuatro cinco\nseis\n"
        self.assertEqual(locate_quote(text, ".md", "tres  cuatro")["line"], 2)
        self.assertEqual(locate_quote(text, ".md", "seis")["line"], 4)


class Validate(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(CROSSES / "pedido_contradiccion.md", root / "pedido.md")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["sources", PID, "--load", str(CROSSES / "prototipo-aprobaciones.html"),
                "--role", "diseno_nuevo", "--change", CID])
        run_ok(["sources", PID, "--load", str(SAD), "--role", "linea_de_base", "--change", CID])

    def ids(self) -> dict[str, str]:
        found = change_sources(PID, CID)
        return {"pedido": found["by_role"]["pedido"][0], "diseno": found["by_role"]["diseno_nuevo"][0],
                "sad": found["baseline"][0]}

    def claims(self, name: str) -> list[dict]:
        ids = self.ids()
        text = (CROSSES / name).read_text(encoding="utf-8").replace("F-PED", ids["pedido"]).replace("F-DIS", ids["diseno"])
        claims, errors = parse_claims(text)
        self.assertEqual(errors, [])
        return claims

    def check(self, kind: str, text: str) -> list[str]:
        claims, errors = parse_claims(text)
        self.assertEqual(errors, [], text)
        _, found = validate_claims(PID, CID, kind, claims)
        return found

    def test_valid_design_and_contradiction_files(self):
        result, errors = validate_claims(PID, CID, "diseno", self.claims("cruce_diseno.md"))
        self.assertEqual(errors, [])
        self.assertEqual(len(result), 5)
        divergence = result[4]
        pedido = divergence["citations"][0]
        self.assertEqual(pedido["path"], "00_raw/09_request/pedido.md")
        text = (workspace_path(PID) / "00_raw" / "09_request" / "pedido.md").read_text(encoding="utf-8").splitlines()
        self.assertIn("RN-02", text[pedido["line"] - 1])
        design = divergence["citations"][1]
        self.assertTrue(design["path"].startswith("00_raw/"))
        self.assertEqual(design["line"], 9)
        result, errors = validate_claims(PID, CID, "contradicciones", self.claims("cruce_contradicciones.md"))
        self.assertEqual(errors, [])
        self.assertEqual(len(result[0]["citations"]), 2)

    def test_role_checks(self):
        ids = self.ids()
        errors = self.check("diseno", f'- [SOLO EN DISEÑO] Algo.\n  - Diseño: {ids["sad"]} "Bandeja de aprobaciones"\n')
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("línea 1:") and "linea_de_base" in errors[0] and "diseno_nuevo" in errors[0], errors)
        errors = self.check("diseno", f'- [SIN RESPALDO EN DISEÑO] Algo.\n  - Pedido: {ids["diseno"]} "Bandeja de aprobaciones de altas"\n')
        self.assertTrue("diseno_nuevo" in errors[0] and "«Pedido:»" in errors[0], errors)
        errors = self.check("diseno", '- [SOLO EN DISEÑO] Algo.\n  - Diseño: F-99 "Bandeja de aprobaciones"\n')
        self.assertEqual(errors, ["línea 1: F-99 no es una fuente registrada"])

    def test_quote_rules(self):
        ids = self.ids()
        errors = self.check("diseno", f'- [SOLO EN DISEÑO] Algo.\n  - Diseño: {ids["diseno"]} "Aprobar"\n')
        self.assertIn("menos de 8 caracteres", errors[0])
        short = "La jefa de Compras no"  # 21: fine; trim to 19
        self.assertGreaterEqual(len(short), 20)
        errors = self.check("diseno", f'- [SIN RESPALDO EN DISEÑO] Algo.\n  - Pedido: {ids["pedido"]} "{short[:19]}"\n')
        self.assertIn("menos de 20 caracteres", errors[0])
        errors = self.check("diseno", f'- [SIN RESPALDO EN DISEÑO] Algo.\n  - Pedido: {ids["pedido"]} "esta cita no está en el pedido"\n')
        self.assertIn("no aparece literal", errors[0])
        errors = self.check("diseno", f'- [SOLO EN DISEÑO] Algo.\n  - Diseño: {ids["diseno"]} "border:1px solid"\n')
        self.assertIn("no aparece literal", errors[0])
        self.assertIn("texto visible del HTML", errors[0])

    def test_tag_and_count_rules(self):
        ids = self.ids()
        quote = '"La jefa de Compras no puede aprobar un alta que cargó ella misma."'
        errors = self.check("diseno", f"- [CONTRADICCIÓN] Algo.\n  - Pedido: {ids['pedido']} {quote}\n"
                                       f"  - Pedido: {ids['pedido']} {quote}\n")
        self.assertIn("no va en el cruce diseno", errors[0])
        errors = self.check("diseno", f"- [DIVERGENCIA] Algo.\n  - Pedido: {ids['pedido']} {quote}\n")
        self.assertIn("lleva una cita Pedido y una Diseño", errors[0])
        errors = self.check("contradicciones", f"- [CONTRADICCIÓN] Algo.\n  - Pedido: {ids['pedido']} {quote}\n"
                                               f"  - Pedido: {ids['pedido']} {quote}\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("lugares distintos", errors[0])
        overlapping = '"no puede aprobar un alta que cargó ella misma."'
        errors = self.check("contradicciones", f"- [CONTRADICCIÓN] Algo.\n  - Pedido: {ids['pedido']} {quote}\n"
                                               f"  - Pedido: {ids['pedido']} {overlapping}\n")
        self.assertIn("lugares distintos", errors[0])

    def test_superseded_source_is_refused(self):
        ids = self.ids()
        copy = Path.cwd() / "prototipo-v2.html"
        copy.write_text(HTML.replace("</body>", "<p>Pantalla nueva de reportes de altas</p>\n</body>"), encoding="utf-8")
        loaded = json.loads(run_ok(["sources", PID, "--load", str(copy), "--role", "diseno_nuevo", "--change", CID]))
        run_ok(["sources", PID, "--id", ids["diseno"], "--superseded-by", loaded["source_id"], "--reason", "x"])
        errors = self.check("diseno", f'- [SOLO EN DISEÑO] Algo.\n  - Diseño: {ids["diseno"]} "Bandeja de aprobaciones"\n')
        self.assertEqual(errors, [f"línea 1: {ids['diseno']} fue reemplazada o retirada: citá la vigente"])
        errors = self.check("diseno", f'- [SOLO EN DISEÑO] Algo.\n  - Diseño: {loaded["source_id"]} "Bandeja de aprobaciones"\n')
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
