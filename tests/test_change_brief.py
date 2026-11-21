"""IMP-386: the change brief template and compiler (pure API; no CLI wiring)."""
from __future__ import annotations

import json
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.compilers.change_brief import (  # noqa: E402
    collect_change_brief_inputs,
    compile_change_brief,
    render_change_brief,
)
from sentinel.pending_marks import count_pending_marks  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCOPE_ANSWER = "\n".join([
    "### GAP-SCOPE",
    "- Respuesta: Sólo el formulario de alta de proveedores.",
    "- Borde:",
    '  - nuevo | pantalla | Botón "Guardar borrador" en el alta de proveedores',
    '  - nuevo | pantalla | Listado "Mis borradores"',
    "  - adyacente | endpoint | Envío actual del alta de proveedores",
    "  - adyacente | dato | Tabla de proveedores",
    "  - preservado | proceso | Envío completo del alta",
    "- Owner / fuente: Jefa de Compras",
    "- Estado de decisión: confirmado",
    "",
])
BACKEND_ONLY_SCOPE = "\n".join([
    "### GAP-SCOPE",
    "- Respuesta: Sólo el servicio de envío.",
    "- Borde:",
    "  - nuevo | endpoint | Guardado de borradores",
    "  - adyacente | dato | Tabla de proveedores",
    "- Owner / fuente: Arquitectura",
    "- Estado de decisión: confirmado",
    "",
])
RULES_ANSWER = "\n".join([
    "### GAP-BUSINESS-RULES",
    "- Respuesta:",
    "  - La carga parcial no exige datos obligatorios | sólo el nombre",
    "  - Se conserva `parcial_id` por 30 días",
    "- Owner / fuente: Jefa de Compras",
    "- Evidencia o referencia: Acta de la reunión de relevamiento",
    "- Estado de decisión: confirmado",
    "",
])
HARVEST = """# Harvest

## B0 Inventory
- repo: compras-api — services/compras
- doc: manual-compras — 00_raw/01_business_context/manual-compras.md

## B2 Servicios
- [HECHO compras-api:src/envio.py] El envio del alta valida los datos fiscales antes de persistir.

## B6 Pantallas
- [HECHO manual-compras:manual-compras.md] El alta de proveedores tiene cuatro pasos.

## B7 Flujos
- [HECHO manual-compras:manual-compras.md] El analista envia el alta y Compras la aprueba.

## B1 Architecture
- [DIVERGENCIA compras-api:README.md] El README dice v2; el codigo sirve rutas v1.
"""
CITE = re.compile(r"GAP-[A-Z0-9-]+|`00_raw/|\b[\w.-]+:[\w./-]+|#GAP-SCOPE|harvest\.json")


def _build(*, scope: str | None = SCOPE_ANSWER, baseline: bool = True, extra: str | None = None,
           harvest: str | None = None) -> None:
    root = Path.cwd()
    shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
    run_ok(["init", "BORR"])
    run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])
    base = workspace_path("BORR")
    if scope:
        (root / "scope.md").write_text(scope, encoding="utf-8")
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", "CHG-001"])
    if baseline:
        raw = base / "00_raw"
        shutil.copy(FIXTURES / "change_baseline" / "sad-compras.md", raw / "02_technology_context" / "sad-compras.md")
        shutil.copy(FIXTURES / "change_baseline" / "manual-compras.md", raw / "01_business_context" / "manual-compras.md")
        shutil.copy(FIXTURES / "change_baseline" / "answers_baseline.md", root / "answers_baseline.md")
        run_ok(["resolve-gaps", "BORR", "--source", "answers_baseline.md", "--change", "CHG-001"])
    if extra:
        (root / "extra.md").write_text(extra, encoding="utf-8")
        run_ok(["resolve-gaps", "BORR", "--source", "extra.md", "--change", "CHG-001"])
    if harvest:
        (root / "h.md").write_text(harvest, encoding="utf-8")
        run_ok(["harvest", "BORR", "--source", "h.md", "--change", "CHG-001"])


def sections(text: str) -> dict[int, str]:
    parts = re.split(r"^## (\d)\. ", text, flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


def bullets(body: str) -> list[str]:
    return [line for line in body.splitlines() if line.startswith("- ")]


def lens_body(s5: str, title: str) -> str:
    return re.search(rf"### {title}\n(.*?)(?=\n### |\Z)", s5, re.S).group(1)


class FullChange(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        _build()

    def brief(self) -> tuple[str, dict]:
        return render_change_brief(collect_change_brief_inputs("BORR", "CHG-001"))

    def test_has_the_nine_sections_in_order(self):
        text, _ = self.brief()
        titles = re.findall(r"^## (\d)\. (.+)$", text, flags=re.M)
        self.assertEqual(
            titles,
            [("1", "Contexto y línea de base"), ("2", "Problema y resultado"), ("3", "Borde"),
             ("4", "Proceso as-is → to-be"), ("5", "Por lente"), ("6", "Comportamiento preservado"),
             ("7", "Reglas y aceptación"), ("8", "Blast radius e impacto"), ("9", "Pendientes")],
        )

    def test_border_lists_zones_with_citations(self):
        text, _ = self.brief()
        s = sections(text)
        cite = "07_changes/00_client_responses/scope.md#GAP-SCOPE"
        self.assertIn(f'pantalla — Botón "Guardar borrador" en el alta de proveedores ({cite})', s[3])
        self.assertIn("endpoint — Envío actual del alta de proveedores (", s[3])
        self.assertNotIn("Envío completo del alta", s[3])
        self.assertIn(f"proceso — Envío completo del alta ({cite})", s[6])
        self.assertIn("Sólo el formulario de alta de proveedores. (GAP-SCOPE)", s[3])

    def test_baseline_closures_show_as_existing_with_quote(self):
        text, _ = self.brief()
        s5 = sections(text)[5]
        self.assertIn(
            "Ya existe: «responde en menos de dos segundos al percentil 95 en horario pico» "
            "(`00_raw/02_technology_context/sad-compras.md`, GAP-TECH-NFR)",
            s5,
        )
        self.assertIn("`00_raw/01_business_context/manual-compras.md`", s5)
        self.assertIn("`00_raw/02_technology_context/sad-compras.md`", sections(text)[1])

    def test_open_gaps_are_pending_marks_and_listed(self):
        text, report = self.brief()
        s = sections(text)
        self.assertIn("⏳ PENDIENTE (GAP-OBJECTIVE)", s[2])
        self.assertIn("⏳ PENDIENTE (GAP-USERS)", s[2])
        self.assertIn("⏳ PENDIENTE (GAP-ACCEPTANCE)", s[7])
        for gap in ("GAP-OBJECTIVE", "GAP-USERS", "GAP-ACCEPTANCE"):
            row = next(line for line in s[9].splitlines() if line.startswith(f"| {gap} "))
            self.assertTrue(row.rstrip().endswith("| sí |"), row)
        self.assertIn("GAP-ACCEPTANCE", report["pending_gaps"])
        self.assertEqual(report["sections"]["2"]["pending"], 2)

    def test_every_content_line_cites_its_origin(self):
        text, _ = self.brief()
        for number, body in sections(text).items():
            if number == 9:
                continue
            for line in bullets(body):
                if line.startswith("- N/A — "):
                    continue  # a counterfactual, not a content line
                self.assertRegex(line, CITE, f"section {number}: {line}")
                self.assertRegex(line.rstrip(), r"\)$", f"section {number}: {line}")

    def test_design_has_content_when_border_has_pantalla(self):
        text, _ = self.brief()
        self.assertNotIn("N/A — el borde no toca Diseño", sections(text)[5])

    def test_pending_count_matches_deliverables_counter(self):
        text, report = self.brief()
        self.assertEqual(count_pending_marks(text).blocking, report["blocking_open"])
        self.assertGreaterEqual(report["blocking_open"], 3)

    def test_compile_writes_brief_and_report_only_in_the_change_folder(self):
        base = workspace_path("BORR")
        out = compile_change_brief("BORR", "CHG-001")
        brief = base / "02_requirements" / "CHG-001" / "project-brief.md"
        report = base / "02_requirements" / "CHG-001" / "change_brief_report.json"
        self.assertEqual(Path(out["path"]).resolve(), brief.resolve())
        self.assertTrue(brief.exists() and report.exists())
        self.assertEqual(json.loads(report.read_text(encoding="utf-8")), out["report"])
        self.assertFalse((base / "02_requirements" / "project-brief.md").exists())
        n = out["report"]["blocking_open"]
        self.assertEqual(out["summary"], {"pending": n, "blocking_open": n})
        self.assertEqual(compile_change_brief("BORR", "CHG-001")["report"], out["report"])

    def test_no_harvest_json_is_fine(self):
        self.assertFalse((workspace_path("BORR") / "01_discovery" / "harvest.json").exists())
        text, _ = self.brief()
        self.assertNotIn("harvest.json", text)
        self.assertNotIn("Repositorio", sections(text)[1])


class ScopeRound(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        _build(scope=None, baseline=False)

    def test_scope_round_change_compiles_with_scope_pending(self):
        text, report = render_change_brief(collect_change_brief_inputs("BORR", "CHG-001"))
        s = sections(text)
        self.assertIn("⏳ PENDIENTE (GAP-SCOPE)", s[3])
        self.assertEqual(text.count("⏳ PENDIENTE (GAP-SCOPE)"), 1)
        self.assertEqual(len(bullets(s[5])), 1)
        self.assertNotRegex(s[5], r"GAP-(?!SCOPE)[A-Z-]+")
        self.assertEqual(count_pending_marks(text).blocking, report["blocking_open"])
        self.assertEqual(report["blocking_open"], 4)  # OBJECTIVE, USERS, SCOPE, ASIS-TOBE
        self.assertEqual(
            set(report["pending_gaps"]),
            {"GAP-OBJECTIVE", "GAP-USERS", "GAP-SCOPE", "GAP-PRODUCT-ASIS-TOBE"},
        )


class BackendOnly(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        _build(scope=BACKEND_ONLY_SCOPE, baseline=False)

    def test_design_na_when_border_has_no_pantalla(self):
        text, report = render_change_brief(collect_change_brief_inputs("BORR", "CHG-001"))
        design = lens_body(sections(text)[5], "Diseño")
        self.assertRegex(
            design,
            r"N/A — el borde no toca Diseño\. Si el borde suma una superficie de Diseño, se abre\.",
        )
        self.assertNotIn("⏳", design)
        self.assertIn("Sin superficies preservadas", sections(text)[6])
        self.assertEqual(count_pending_marks(text).blocking, report["blocking_open"])


class MultilineAnswer(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        _build(baseline=False, extra=RULES_ANSWER)

    def test_multiline_and_pipe_answers_stay_intact(self):
        text, _ = render_change_brief(collect_change_brief_inputs("BORR", "CHG-001"))
        line = next(item for item in bullets(sections(text)[7]) if "GAP-BUSINESS-RULES" in item)
        self.assertEqual(
            line,
            "- La carga parcial no exige datos obligatorios | sólo el nombre; Se conserva `parcial_id` por 30 días (GAP-BUSINESS-RULES)",
        )


class WithHarvest(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        _build(harvest=HARVEST)

    def test_harvest_facts_follow_the_border_surfaces(self):
        text, report = render_change_brief(collect_change_brief_inputs("BORR", "CHG-001"))
        s = sections(text)
        self.assertIn("Repositorio: compras-api", s[1])
        self.assertIn("Documento: manual-compras", s[1])
        # B7 flows in section 4 (once); B6 under design (pantalla); B2 under technical (endpoint, dato).
        self.assertIn("El analista envia el alta y Compras la aprueba. (manual-compras:manual-compras.md, B7)", s[4])
        self.assertNotIn("El analista envia", s[5])
        self.assertIn("El alta de proveedores tiene cuatro pasos. (manual-compras:manual-compras.md, B6)", s[5])
        self.assertIn("El envio del alta valida los datos fiscales antes de persistir. (compras-api:src/envio.py, B2)", s[5])
        self.assertNotIn("El alta de proveedores tiene cuatro pasos", s[4])
        # The harvest divergence is a change gap: it lands in section 8 as a pending mark.
        self.assertRegex(s[8], r"⏳ PENDIENTE \(GAP-HRV-[0-9A-F]+\)")
        self.assertEqual(count_pending_marks(text).blocking, report["blocking_open"])
        for number, body in s.items():
            if number != 9:
                for line in bullets(body):
                    if not line.startswith("- N/A — "):
                        self.assertRegex(line, CITE, line)


if __name__ == "__main__":
    unittest.main()
