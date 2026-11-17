"""IMP-350: /dashboard renders in the project language, not always in Spanish.

Rule: each workspace card, drawer and modal speaks its own workspace's language
(state.json ``project_language``; any ``es*`` tag is Spanish, anything else
English). The page frame (header, indicators, filters, menu, legend) uses the
language most workspaces use; a tie or an empty folder gives English. The
provenance section's wording belongs to IMP-346 (shell.provenance_section) and
is left out of the "no Spanish left" check here.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from sentinel import themes
from sentinel import dashboard
from sentinel.dashboard import collect_dashboard_model, portfolio_language, render_dashboard, validate_dashboard_model, workspace_language
from tests.test_dashboard import DashboardFixtureMixin
from tests.test_dashboard_shell import pin_mtimes

GOLDEN_EN = Path(__file__).resolve().parent / "fixtures" / "golden" / "dashboard" / "portfolio-en.html"
UPDATE = os.environ.get("SENTINEL_UPDATE_GOLDEN") == "1"

# Spanish UI strings the dashboard used to print. None may survive in an English page.
SPANISH_LABELS = [
    "Indicadores", "Procedencia", "Leyenda", "Secciones", "Proximo paso", "Requieren atencion", "Requiere atencion",
    "Gaps bloqueantes", "Listos para avanzar", "User stories totales", "Buscar workspace", "Toda la cartera", "Todos",
    "Copiar prompt", "Comando de terminal", "Gaps abiertos", "Gaps cerrados", "Madurez", "Resumen", "Documentos",
    "Fecha de corte", "Regenerar", "Corte de fuentes", "datos embebidos", "Copiado", "Respuesta:", "bloqueado",
    "en curso", "(hoy)", "(hace ", "Acciones segun", "El cliente respondio", "Idioma", "Certeza desarrollo",
    "Estado actual", "Saltar al contenido", "Lifecycle de maduracion", "Cargar el requerimiento", "Preparar backlog",
    "Esperando respuestas", "esperando respuesta", "listo para generar", "Inspeccionar estado", "Gaps pendientes",
    "Generado: ", "Abrir archivo original", "Copiar markdown", "Falta", "Origen: snapshot", "actualizado",
    "No hay workspaces", "Sin workspaces", "fuente de verdad", "de un vistazo", "pendientes:", "abiertos o parciales",
    "Ingesta", "Calidad (AC/DoD)", "Historias de usuario", "Especificaciones funcionales",
]
ENGLISH_LABELS = ["Next step", "Need attention", "Open gaps", "Provenance", "Colour legend", "Copy prompt", "Maturity lifecycle"]


def without_provenance(html: str) -> str:
    """The page minus its provenance <section>, whose wording IMP-346 owns (shell.provenance_section)."""
    start = html.index('<section class="dash-section" id="provenance"')
    return html[:start] + html[html.index("</section>", start) + len("</section>") :]


class _LanguageFixture(DashboardFixtureMixin):
    def set_languages(self, **languages: str) -> None:
        for project_id, language in languages.items():
            path = self.temp / "workspaces" / project_id / "state.json"
            state = json.loads(path.read_text(encoding="utf-8"))
            state["project_language"] = language
            path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        pin_mtimes(self.temp)

    def render(self) -> tuple[dict, str]:
        model = collect_dashboard_model(self.temp)
        return model, render_dashboard(model, themes.load_theme())


class EnglishDashboardTests(_LanguageFixture, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.set_languages(DASH_CLIENT_WAIT="en", DASH_BACKLOG_READY="en")
        self.model, self.html = self.render()

    def test_no_spanish_ui_string_is_left(self) -> None:
        page = self.html  # the provenance section follows the page language too
        left = [label for label in SPANISH_LABELS if label in page]
        self.assertEqual(left, [], "Spanish UI strings in an English dashboard")

    def test_page_is_marked_english(self) -> None:
        self.assertEqual(self.model["language"], "en")
        self.assertIn('<html lang="en"', self.html)
        self.assertIn(themes.legend_html(themes.load_theme(), "en"), self.html)
        for label in ENGLISH_LABELS:
            self.assertIn(label, self.html)

    def test_workspace_copy_is_english(self) -> None:
        waiting = next(w for w in self.model["workspaces"] if w["project_id"] == "DASH_CLIENT_WAIT")
        self.assertEqual(waiting["language"], "en")
        self.assertEqual(waiting["next_title"], "Waiting for client answers")
        self.assertEqual(waiting["lifecycle"]["text"], "Discovery - waiting for the client's answers")
        self.assertIn("Open gaps", waiting["summary"])
        self.assertEqual(waiting["steps"][0]["label"], "Ingest")
        self.assertEqual(validate_dashboard_model(self.model), [])

    def test_english_golden(self) -> None:
        if UPDATE:
            GOLDEN_EN.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN_EN.write_text(self.html, encoding="utf-8", newline="\n")
            return
        self.assertTrue(GOLDEN_EN.exists(), f"missing golden {GOLDEN_EN}; create it with SENTINEL_UPDATE_GOLDEN=1")
        self.assertEqual(self.html, GOLDEN_EN.read_text(encoding="utf-8"), "English dashboard drifted from its golden")


class SpanishDashboardTests(_LanguageFixture, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.set_languages(DASH_CLIENT_WAIT="es", DASH_BACKLOG_READY="es")
        self.model, self.html = self.render()

    def test_spanish_page_keeps_its_labels(self) -> None:
        self.assertEqual(self.model["language"], "es")
        self.assertIn('<html lang="es"', self.html)
        for label in ("Indicadores", "Procedencia", "Leyenda de colores", "Requieren atencion", "Proximo paso", "Buscar workspace...", "Fecha de corte:"):
            self.assertIn(label, self.html)
        for label in ENGLISH_LABELS:
            self.assertNotIn(label, self.html)

    def test_spanish_workspace_copy_is_unchanged(self) -> None:
        waiting = next(w for w in self.model["workspaces"] if w["project_id"] == "DASH_CLIENT_WAIT")
        self.assertEqual(waiting["next_title"], "Esperando respuestas del cliente")
        self.assertEqual(waiting["lifecycle"]["text"], dashboard.LIFECYCLE_STAGES["CLIENT_RESPONSE_NEEDED"]["text"])
        self.assertEqual(waiting["steps"], dashboard.STEPS)
        self.assertEqual(waiting["scenarios"][0]["title"], dashboard.SCENARIOS[0]["title"])


class MixedPortfolioTests(_LanguageFixture, unittest.TestCase):
    def test_each_workspace_keeps_its_language(self) -> None:
        self.set_languages(DASH_CLIENT_WAIT="es", DASH_BACKLOG_READY="en")
        model, html = self.render()
        by_id = {w["project_id"]: w for w in model["workspaces"]}
        self.assertEqual(by_id["DASH_CLIENT_WAIT"]["next_title"], "Esperando respuestas del cliente")
        self.assertIn("Gaps abiertos", by_id["DASH_CLIENT_WAIT"]["summary"])
        ready = by_id["DASH_BACKLOG_READY"]
        self.assertEqual(ready["next_title"], dashboard.NEXT_ACTION_COPY_EN[ready["next_action"]["key"]][0])
        self.assertIn("Open gaps", by_id["DASH_BACKLOG_READY"]["summary"])
        marker = '<script id="dashboard-i18n" type="application/json">'
        start = html.index(marker) + len(marker)
        i18n = json.loads(html[start : html.index("</script>", start)])
        self.assertEqual(sorted(i18n), ["en", "es"], "both tables travel when both languages are used")

    def test_tie_gives_an_english_frame(self) -> None:
        self.set_languages(DASH_CLIENT_WAIT="es", DASH_BACKLOG_READY="en")
        model, html = self.render()
        self.assertEqual(model["language"], "en")
        self.assertIn('<html lang="en"', html)

    def test_majority_sets_the_frame(self) -> None:
        self.set_languages(DASH_CLIENT_WAIT="es", DASH_BACKLOG_READY="auto")
        self.assertEqual(collect_dashboard_model(self.temp)["language"], "en")  # auto is English, then a tie
        self.assertEqual(portfolio_language(["es", "es", "en"]), "es")
        self.assertEqual(portfolio_language(["en", "es", "en"]), "en")
        self.assertEqual(portfolio_language(["es", "en"]), "en")
        self.assertEqual(portfolio_language([]), "en")

    def test_any_spanish_tag_is_spanish(self) -> None:
        self.assertEqual([workspace_language(v) for v in ("es", "es-AR", "ES", "en", "auto", None, "")], ["es", "es", "es", "en", "en", "en", "en"])
        self.set_languages(DASH_CLIENT_WAIT="es-AR", DASH_BACKLOG_READY="es")
        self.assertEqual(collect_dashboard_model(self.temp)["language"], "es")

    def test_one_language_ships_one_table(self) -> None:
        self.set_languages(DASH_CLIENT_WAIT="en", DASH_BACKLOG_READY="en")
        _model, html = self.render()
        self.assertNotIn('"es":', html[html.index('id="dashboard-i18n"') :])


class StringTableTests(unittest.TestCase):
    def test_tables_cover_both_languages_with_the_same_keys(self) -> None:
        for name in ("PAGE_TEXT", "UI_TEXT", "SUMMARY_LABELS"):
            table = getattr(dashboard, name)
            self.assertEqual(sorted(table), ["en", "es"], name)
            self.assertEqual(sorted(table["es"]), sorted(table["en"]), name)
        self.assertEqual(sorted(dashboard.LIFECYCLE_TEXT_EN), sorted(dashboard.LIFECYCLE_STAGES))
        self.assertEqual(sorted(dashboard.NEXT_ACTION_COPY_EN), sorted(dashboard.NEXT_ACTION_COPY))
        self.assertEqual(sorted(dashboard.SECTION_TITLES_EN), sorted(s.key for s in dashboard.SECTION_REGISTRY))
        self.assertEqual([s["key"] for s in dashboard.STEPS_EN], [s["key"] for s in dashboard.STEPS])
        self.assertEqual(len(dashboard.SCENARIOS_EN), len(dashboard.SCENARIOS))

    def test_english_commands_match_spanish_commands(self) -> None:
        for key, (_title, command, _prompt) in dashboard.NEXT_ACTION_COPY.items():
            self.assertEqual(dashboard.NEXT_ACTION_COPY_EN[key][1], command, key)
        for es, en in zip(dashboard.SCENARIOS, dashboard.SCENARIOS_EN):
            self.assertEqual(es["command"], en["command"])

    def test_the_script_has_no_hard_coded_spanish(self) -> None:
        from sentinel.resources import package_resource

        for name in ("dashboard.js", "dashboard-page.html"):
            text = package_resource("themes", "templates", name).read_text(encoding="utf-8")
            left = [label for label in SPANISH_LABELS if label in text]
            self.assertEqual(left, [], name)


if __name__ == "__main__":
    unittest.main()
