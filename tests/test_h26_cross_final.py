"""IMP-404 (H26 inc 4) final fix wave: C1, I1-I6, the status/report fixes and the quote handling."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_h26_cross_record as record_tests  # noqa: E402
import test_h26_cross_surfaces as surface_tests  # noqa: E402
from helpers import run_ok  # noqa: E402

from sentinel.changes import change_gaps_path, get_change, list_changes, regenerate_change_gaps  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses import crosses_dir  # noqa: E402
from sentinel.crosses.claims import locate_quote, parse_claims  # noqa: E402
from sentinel.crosses.record import CrossError, load_cross, record_cross, skip_cross  # noqa: E402
from sentinel.crosses.state import _cite_text, cross_status, crosses_fingerprint  # noqa: E402
from sentinel.crosses.surfaces import accept_new_surface, decline_new_surface  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.status import _extraction_warnings  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

PID = record_tests.PID
CID = record_tests.CID
SURF_PID = surface_tests.PID
NL = chr(10)


def write_file(name: str, text: str) -> Path:
    path = Path.cwd() / name
    path.write_text(text, encoding="utf-8")
    return path


class ParseFormat(unittest.TestCase):
    """I1 and the quote forms."""

    def test_bold_claim_is_accepted(self):
        text = NL.join(['- **[DIVERGENCIA]** El umbral no coincide.',
                        '  - Pedido: F-01 "texto de pedido"', '  - Diseño: F-02 "texto de diseño"', ""])
        claims, errors = parse_claims(text)
        self.assertEqual(errors, [])
        self.assertEqual([c["tag"] for c in claims], ["divergencia"])
        self.assertEqual(len(claims[0]["citations"]), 2)

    def test_numbered_claim_is_an_error_not_swallowed(self):
        text = NL.join([
            '- [SOLO EN DISEÑO] Delega aprobaciones.', '  - Diseño: F-02 "Delegar aprobaciones"',
            '1. [DIVERGENCIA] El umbral no coincide.', '  - Pedido: F-01 "mayor a 5.000.000 requiere"',
            '  - Diseño: F-02 "Umbral de aprobación: 1.000.000"', ""])
        claims, errors = parse_claims(text)
        self.assertTrue(any(e.startswith("línea 3: afirmación mal escrita") for e in errors), errors)
        self.assertEqual(len(claims), 1)
        self.assertEqual(len(claims[0]["citations"]), 1)  # the quotes of line 3 are nobody's

    def test_malformed_claim_in_english(self):
        _, errors = parse_claims("1. [DIVERGENCE] x" + NL, "en")
        self.assertTrue(any(e.startswith("line 1: malformed claim") for e in errors), errors)

    def test_guillemets_and_inner_double_quotes(self):
        text = NL.join([
            '- [SIN RESPALDO EN DISEÑO] a', '  - Pedido: F-01 «quiero ver las altas pendientes»',
            '- [SIN RESPALDO EN DISEÑO] b', '  - Pedido: F-01 "el campo "Motivo" es obligatorio"', ""])
        claims, errors = parse_claims(text)
        self.assertEqual(errors, [])
        self.assertEqual(claims[0]["citations"][0]["quote"], "quiero ver las altas pendientes")
        self.assertEqual(claims[1]["citations"][0]["quote"], 'el campo "Motivo" es obligatorio')

    def test_malformed_quote_error_lists_the_valid_forms(self):
        _, errors = parse_claims(NL.join(["- [SIN RESPALDO EN DISEÑO] a", "  - Pedido: F-01 sin comillas", ""]))
        self.assertIn("«…»", errors[0])

    def test_nothing_found_tag_parses(self):
        claims, errors = parse_claims("- [SIN HALLAZGOS] Leí el pedido entero." + NL)
        self.assertEqual(errors, [])
        self.assertEqual(claims[0]["tag"], "sin_hallazgos")


class HtmlQuotes(unittest.TestCase):
    HTML = ('<html><body><p>Umbral de <b>aprobación</b>: 1.000.000</p>'
            '<textarea placeholder="Motivo del rechazo"></textarea>'
            '<img alt="Logo de la empresa" src="x.png"></body></html>')

    def test_inline_tags_do_not_split_the_text(self):
        self.assertIsNotNone(locate_quote(self.HTML, ".html", "Umbral de aprobación: 1.000.000"))
        self.assertIsNotNone(locate_quote(self.HTML, ".html", "aprobación : 1.000.000"))

    def test_attribute_text_is_citable(self):
        self.assertIsNotNone(locate_quote(self.HTML, ".html", "Motivo del rechazo"))
        self.assertIsNotNone(locate_quote(self.HTML, ".html", "Logo de la empresa"))

    def test_hidden_and_markup_are_not(self):
        html = '<script>var x = "texto oculto de script";</script><p class="nombre-de-clase">hola mundo</p>'
        self.assertIsNone(locate_quote(html, ".html", "texto oculto de script"))
        self.assertIsNone(locate_quote(html, ".html", "nombre-de-clase"))


class Pure(unittest.TestCase):
    def test_report_squashes_a_quote_with_a_line_break(self):
        quote = "dos  líneas" + NL + "  juntas"
        text = _cite_text({"side": "pedido", "source_id": "F-01", "line": 3, "quote": quote}, "es")
        self.assertEqual(text, "Pedido F-01:3 «dos líneas juntas»")


class Final(record_tests.CrossCase):
    def contradiction_file(self, name: str = "cruce_contradicciones.md") -> Path:
        return self.write("cruce_contradicciones.md")  # each call files a new copy, so a new F-NN

    # C1
    def test_nothing_found_is_a_done_cross(self):
        file = write_file("nada.md", "- [SIN HALLAZGOS] Leí el pedido entero: no se contradice." + NL)
        result = record_cross(PID, CID, "contradicciones", file)
        self.assertEqual(result["gaps"], [])
        info = cross_status(PID, CID)["kinds"]["contradicciones"]
        self.assertEqual(info["state"], "done")
        self.assertEqual(info["counts"], {"sin_hallazgos": 1})
        self.assertIn("SIN HALLAZGOS 1", cross_status(PID, CID)["text"])
        report = (crosses_dir(workspace_path(PID), CID) / "crosses.md").read_text(encoding="utf-8")
        self.assertIn("- [SIN HALLAZGOS] Leí el pedido entero: no se contradice.", report)

    def test_nothing_found_stands_alone(self):
        body = self.contradiction_file().read_text(encoding="utf-8")
        text = "- [SIN HALLAZGOS] Nada." + NL + body
        with self.assertRaises(CrossError) as caught:
            record_cross(PID, CID, "contradicciones", write_file("mezcla.md", text))
        self.assertIn("va solo", str(caught.exception))

    def test_nothing_found_in_english(self):
        record_tests.set_language(PID, "en")
        file = write_file("nothing.md", "- [NOTHING FOUND] Read the whole request." + NL)
        record_cross(PID, CID, "diseno", file)
        self.assertEqual(cross_status(PID, CID)["kinds"]["diseno"]["counts"], {"sin_hallazgos": 1})

    def test_stale_cross_can_be_waived_and_a_current_one_cannot(self):
        record_cross(PID, CID, "contradicciones", self.contradiction_file())
        with self.assertRaises(InputError):
            skip_cross(PID, CID, "contradicciones", "no aplica")
        self.load_addendum()
        self.assertEqual(cross_status(PID, CID)["kinds"]["contradicciones"]["state"], "stale")
        result = skip_cross(PID, CID, "contradicciones", "la adenda no cambia nada")
        self.assertEqual(result["action"], "skip")
        info = cross_status(PID, CID)["kinds"]["contradicciones"]
        self.assertEqual((info["state"], info["reason"]), ("waived", "la adenda no cambia nada"))
        # the question the first delivery opened stays open and is carried in the waiver
        kept = load_cross(workspace_path(PID), CID, "contradicciones")["dropped_gaps"]
        self.assertTrue(kept[0].startswith("GAP-CON-"))

    # I2
    def load_addendum(self) -> str:
        file = write_file("adenda.md", "# Adenda al pedido" + NL + NL
                          + "La jefa de Compras también recibe un aviso por cada alta que rechaza." + NL)
        loaded = json.loads(run_ok(["sources", PID, "--load", str(file), "--role", "pedido", "--change", CID]))
        forget_read_snapshots()
        return loaded["source_id"]

    def test_a_new_request_source_makes_both_crosses_stale(self):
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        record_cross(PID, CID, "contradicciones", self.contradiction_file())
        self.assertNotIn("diseno", cross_status(PID, CID)["missing"])
        self.assertNotIn("contradicciones", cross_status(PID, CID)["missing"])
        added = self.load_addendum()
        status = cross_status(PID, CID)
        for kind in ("diseno", "contradicciones"):
            self.assertEqual(status["kinds"][kind]["state"], "stale")
            self.assertEqual(status["kinds"][kind]["new_sources"], [added])
            self.assertEqual(status["kinds"][kind]["stale_sources"], [])
        self.assertEqual(status["missing"][-2:], ["diseno", "contradicciones"])

    def test_recording_again_after_a_new_source_clears_the_stale(self):
        record_cross(PID, CID, "contradicciones", self.contradiction_file())
        self.load_addendum()
        record_cross(PID, CID, "contradicciones", self.contradiction_file())
        self.assertEqual(cross_status(PID, CID)["kinds"]["contradicciones"]["state"], "done")

    def test_a_waiver_goes_stale_with_a_new_source_too(self):
        skip_cross(PID, CID, "contradicciones", "sin contradicciones")
        self.assertEqual(cross_status(PID, CID)["kinds"]["contradicciones"]["state"], "waived")
        self.load_addendum()
        self.assertEqual(cross_status(PID, CID)["kinds"]["contradicciones"]["state"], "stale")

    # I3
    def test_accept_new_takes_a_solo_en_diseno_question(self):
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        sed = next(g for g in self.gaps() if g.startswith("GAP-SED-"))
        result = accept_new_surface(PID, CID, sed, "pantalla", "Delegar aprobaciones")
        self.assertEqual(result["surface"]["origin"], "cross")
        self.assertIn(self.ids()["diseno"], result["surface"]["cite"])
        self.assertTrue(result["surface"]["cite"].startswith("cruce diseno"))
        border = list_changes(PID)[CID]["border"]
        self.assertEqual(border[-1]["name"], "Delegar aprobaciones")
        self.assertEqual(self.gaps()[sed]["status"].strip("`").upper(), "CLOSED")
        self.assertEqual(list_changes(PID)[CID]["new_surfaces"][sed]["decision"], "accepted")
        with self.assertRaises(InputError):
            accept_new_surface(PID, CID, sed, "pantalla", "Otro nombre")

    def test_accept_new_rejects_a_gap_that_is_not_solo_en_diseno(self):
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        dis = next(g for g in self.gaps() if g.startswith("GAP-DIS-"))
        with self.assertRaises(InputError):
            accept_new_surface(PID, CID, dis, "pantalla", "Algo")
        with self.assertRaises(InputError):
            accept_new_surface(PID, CID, "GAP-SED-00000000", "pantalla", "Algo")

    # I5
    def test_fingerprint_survives_a_byte_identical_redelivery(self):
        record_cross(PID, CID, "contradicciones", self.contradiction_file())
        first = crosses_fingerprint(PID, CID)
        self.assertTrue(first)
        before = load_cross(workspace_path(PID), CID, "contradicciones")["source_id"]
        again = self.contradiction_file()
        again.write_text(again.read_text(encoding="utf-8") + "   " + NL + NL, encoding="utf-8")  # same claims, other bytes
        record_cross(PID, CID, "contradicciones", again)
        self.assertNotEqual(load_cross(workspace_path(PID), CID, "contradicciones")["source_id"], before)
        self.assertEqual(crosses_fingerprint(PID, CID), first)

    def test_fingerprint_follows_the_waiver_reason(self):
        skip_cross(PID, CID, "contradicciones", "primer motivo")
        first = crosses_fingerprint(PID, CID)
        skip_cross(PID, CID, "contradicciones", "segundo motivo")
        self.assertNotEqual(crosses_fingerprint(PID, CID), first)

    # minor 3
    def test_a_utf16_file_is_a_cross_error(self):
        path = Path.cwd() / "utf16.md"
        path.write_bytes(("- [SIN HALLAZGOS] Nada." + NL).encode("utf-16"))
        with self.assertRaises(CrossError) as caught:
            record_cross(PID, CID, "contradicciones", path)
        self.assertIn("UTF-8", str(caught.exception))

    def test_guillemets_validate_in_a_real_cross(self):
        ids = self.ids()
        text = NL.join([
            "- [SIN RESPALDO EN DISEÑO] Sin pantalla.",
            "  - Pedido: " + ids["pedido"] + " «quiero consultar quién aprobó cada alta y cuándo»",
            "- [SOLO EN DISEÑO] Delegar.",
            "  - Diseño: " + ids["diseno"] + ' "Delegar aprobaciones"', ""])
        result = record_cross(PID, CID, "diseno", write_file("comillas.md", text))
        self.assertEqual(result["counts"], {"sin_respaldo": 1, "solo_en_diseno": 1})

    def test_bad_claim_line_rejects_the_whole_file(self):
        ids = self.ids()
        text = NL.join([
            "- [SOLO EN DISEÑO] Delegar.", "  - Diseño: " + ids["diseno"] + ' "Delegar aprobaciones"',
            "1. [DIVERGENCIA] El umbral.", "  - Pedido: " + ids["pedido"] + ' "mayor a 5.000.000 requiere aprobación"',
            "  - Diseño: " + ids["diseno"] + ' "Umbral de aprobación: 1.000.000"', ""])
        with self.assertRaises(CrossError) as caught:
            record_cross(PID, CID, "diseno", write_file("numerada.md", text))
        self.assertIn("línea 3", str(caught.exception))
        self.assertIsNone(load_cross(workspace_path(PID), CID, "diseno"))

    # FINAL-WAVE a
    def test_orphans_alone_do_not_report_an_incomplete_extraction(self):
        change = get_change(PID, CID)
        extraction = {"state": "current", "complete": False, "covered": 4, "total": 4, "text": "4 de 4",
                      "orphans": [{"id": "E-09"}], "unreadable": []}
        triggers = [w["trigger"] for w in _extraction_warnings(PID, CID, change, extraction, {"missing": []})]
        self.assertIn("extraction_orphans", triggers)
        self.assertNotIn("extraction_incomplete", triggers)
        extraction.update(covered=3, text="3 de 4")
        triggers = [w["trigger"] for w in _extraction_warnings(PID, CID, change, extraction, {"missing": []})]
        self.assertIn("extraction_incomplete", triggers)


class SurfaceFinal(surface_tests.SurfaceCase):
    def lens_gaps(self) -> set[str]:
        path = change_gaps_path(workspace_path(SURF_PID), "CHG-001")
        return {g["id"] for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g["id"] != "NONE"}

    # I4
    def set_border_types(self, kinds: list[str]) -> None:
        changes = {key: dict(value) for key, value in list_changes(SURF_PID).items()}
        changes["CHG-001"]["border"] = [{"zone": "nuevo", "type": kind, "name": f"Superficie {n}", "cite": "x"}
                                        for n, kind in enumerate(kinds)]
        update_state(SURF_PID, changes=changes)

    def test_prune_drops_unanswered_lens_questions_of_a_type_the_border_lost(self):
        full = self.lens_gaps()
        self.set_border_types(["regla"])
        regenerate_change_gaps(SURF_PID, "CHG-001")
        self.assertEqual(self.lens_gaps(), full)  # without prune nothing leaves
        regenerate_change_gaps(SURF_PID, "CHG-001", prune=True)
        left = self.lens_gaps()
        self.assertLess(len(left), len(full))
        self.assertTrue(left)
        counts = list_changes(SURF_PID)["CHG-001"]["gap_counts"]
        self.assertGreaterEqual(counts["open"], 0)

    def test_declining_an_accepted_surface_regenerates_the_questions(self):
        before = self.lens_gaps()
        cid = self.historial()
        accept_new_surface(SURF_PID, "CHG-001", cid, "integración", "Historial de aprobaciones")
        decline_new_surface(SURF_PID, "CHG-001", cid, "mejor no")
        self.assertEqual(self.lens_gaps(), before)
        self.assertFalse(any(i.get("candidate") == cid for i in list_changes(SURF_PID)["CHG-001"]["border"]))

    def test_empty_folded_name_is_refused(self):
        with self.assertRaises(InputError):
            accept_new_surface(SURF_PID, "CHG-001", self.historial(), "pantalla", chr(0x301))


if __name__ == "__main__":
    unittest.main()
