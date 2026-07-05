"""Regression: /validate must not report false structural findings on a
Spanish-language workspace (H5 campaign finding BUG-01).

The Spanish PRD compiler emits sentence-case headings ("## 1. Resumen
ejecutivo y planteamiento del problema") while the structural validator
anchored on title-case ("Resumen Ejecutivo") with a case-sensitive substring
check, so every Spanish workspace was reported INVALID with
"PRD missing section: Resumen Ejecutivo/Executive Summary."
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.validation import validate_project


RAW_ES = """Requerimiento inicial: Tablero de riesgo operativo

Objetivo: reducir el tiempo de preparación de la revisión semanal de los líderes de soporte.

Usuarios: líderes del equipo de soporte.

Alcance: tablero de solo lectura con volumen de tickets y riesgo de incumplimiento de SLA. Fuera de alcance: editar tickets.

Métrica: reducir el esfuerzo de preparación un 30 por ciento en el primer mes, medido con el reporte semanal existente.
"""


class SpanishPrdValidationTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw_es.md"
        self.raw.write_text(RAW_ES, encoding="utf-8")

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _answer_all_open_gaps(self, project_id: str) -> Path:
        gaps_text = (self.temp / "workspaces" / project_id / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        gap_ids = list(dict.fromkeys(re.findall(r"\bGAP-[A-Z0-9-]+\b", gaps_text)))
        blocks = []
        for gid in gap_ids:
            blocks.append(
                f"### {gid}\n"
                f"- Respuesta: Confirmado por el sponsor: el detalle operativo, los umbrales y el responsable de {gid} quedan definidos en el acta de la mesa de trabajo.\n"
                "- Owner / fuente: Sponsor del cliente\n"
                "- Evidencia o referencia: acta mesa de trabajo\n"
                "- Estado de decisión: confirmado\n"
            )
        answers = self.temp / "respuestas.md"
        answers.write_text("# Respuestas\n\n" + "\n".join(blocks), encoding="utf-8")
        return answers

    def test_spanish_workspace_reaches_valid_without_false_prd_section_findings(self):
        project_id = "TABLERO_ES"
        self.assertEqual(main(["init", project_id]), 0)
        self.assertEqual(main(["ingest", project_id, "--source", str(self.raw)]), 0)
        answers = self._answer_all_open_gaps(project_id)
        self.assertEqual(main(["resolve-gaps", project_id, "--source", str(answers)]), 0)
        self.assertEqual(main(["brief", project_id]), 0)
        self.assertEqual(main(["specs", project_id]), 0)

        prd_text = (self.temp / "workspaces" / project_id / "03_specs" / "prd.md").read_text(encoding="utf-8")
        self.assertIn("Resumen ejecutivo", prd_text)  # Spanish compiler path exercised

        result = validate_project(project_id)

        prd_findings = [f for f in result.get("findings", []) if "PRD missing section" in f]
        self.assertEqual(prd_findings, [])
        self.assertEqual(result["verdict"], "VALID")
