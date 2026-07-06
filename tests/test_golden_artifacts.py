"""IMP-175: golden/snapshot tests for the generated artifacts (project brief, PRD,
specs, backlog) in English AND Spanish.

These replace the 9 dead `sentinel/templates/*.md`: the golden IS the documented,
executable single source of truth for the compiled markdown shape, killing the
`template != compiler != validator` drift class (BUG-01 lived exactly there).
Both languages are pinned because BUG-01 existed only because the evals were
English-only — a Spanish compiler path with no snapshot.

The lifecycle is driven to a mature workspace via EARS acceptance answers (the
functional route that reaches `/backlog`). Output is normalized (project id,
timestamps) so it is stable and readable. Generation is pinned to the json-hybrid
memory backend so the golden is identical whether or not lancedb is installed.

Regenerate intentionally with `SENTINEL_UPDATE_GOLDEN=1` and review the git diff.
"""

import contextlib
import io
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.memory import ContextBroker

GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"
UPDATE = os.environ.get("SENTINEL_UPDATE_GOLDEN") == "1"

ARTIFACTS = {
    "project-brief.md": "02_requirements/project-brief.md",
    "prd.md": "03_specs/prd.md",
    "specs.md": "03_specs/specs.md",
    "backlog.md": "04_backlog/BACKLOG.md",
}

RAW_EN = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: read-only risk dashboard for open queues. Out of scope: editing cases.

Metric: reduce manual preparation by 30 percent in the first release month.
"""

RAW_ES = """# Tablero de riesgo operativo

Objetivo: que los lideres de operaciones revisen las colas de riesgo antes de la reunion diaria.

Usuarios: lideres de operaciones.

Alcance: tablero de solo lectura de colas abiertas. Fuera de alcance: editar casos.

Metrica: reducir la preparacion manual un 30 por ciento en el primer mes de release.
"""

SCENARIOS = {
    "en": {
        "project_id": "GOLDEN_EN",
        "raw": RAW_EN,
        "ears": [
            "When queue metrics are available, the system shall display open risk queues.",
            "When a case breaches SLA, the system shall flag the queue as high risk.",
            "When a queue has no open cases, the system shall hide risk indicators.",
            "While risk data is stale, the system shall show a stale data warning.",
            "If the metrics service is unavailable, then the system shall show risk status unknown.",
            "Where audit logging is enabled, the system shall record dashboard access.",
        ],
        "answer": (
            "### GAP-ACCEPTANCE\n- Answer: {s}\n- Owner / source: Client workshop\n"
            "- Evidence or reference: EARS {i}\n- Decision status: confirmed\n"
        ),
    },
    "es": {
        "project_id": "GOLDEN_ES",
        "raw": RAW_ES,
        "ears": [
            "Cuando haya metricas de cola disponibles, el sistema debe mostrar las colas de riesgo abiertas.",
            "Cuando un caso incumpla el SLA, el sistema debe marcar la cola como riesgo alto.",
            "Cuando una cola no tenga casos abiertos, el sistema debe ocultar los indicadores de riesgo.",
            "Mientras los datos de riesgo esten desactualizados, el sistema debe mostrar una advertencia de datos obsoletos.",
            "Si el servicio de metricas no esta disponible, entonces el sistema debe mostrar estado de riesgo desconocido.",
            "Donde el registro de auditoria este habilitado, el sistema debe registrar el acceso al tablero.",
        ],
        # Field labels the runtime parses in Spanish (see sentinel/gaps.py).
        "answer": (
            "### GAP-ACCEPTANCE\n- Respuesta: {s}\n- Owner / fuente: Taller con cliente\n"
            "- Evidencia o referencia: EARS {i}\n- Estado de decisión: confirmado\n"
        ),
    },
}


def _normalize(text: str, project_id: str) -> str:
    text = text.replace(project_id, "[PROJECT_ID]")
    text = re.sub(
        r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:[+-]\d\d:?\d\d|Z)?",
        "[TIMESTAMP]",
        text,
    )
    text = re.sub(r"\d{4}-\d\d-\d\d", "[DATE]", text)
    return text


def _generate(scenario: dict) -> dict[str, str]:
    from sentinel.cli import main

    pid = scenario["project_id"]
    old_cwd = Path.cwd()
    tmp = Path(tempfile.mkdtemp())
    os.chdir(tmp)
    try:
        raw = tmp / "raw.md"
        raw.write_text(scenario["raw"], encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            if main(["init", pid]) != 0:
                raise AssertionError("init failed")
            if main(["ingest", pid, "--source", str(raw)]) != 0:
                raise AssertionError("ingest failed")
            for index, statement in enumerate(scenario["ears"], start=1):
                answer = tmp / f"answer-{index}.md"
                answer.write_text(scenario["answer"].format(s=statement, i=index), encoding="utf-8")
                if main(["resolve-gaps", pid, "--source", str(answer)]) != 0:
                    raise AssertionError(f"resolve-gaps {index} failed")
            for command in ("brief", "specs", "backlog"):
                if main([command, pid]) != 0:
                    raise AssertionError(f"{command} failed")
        workspace = tmp / "workspaces" / pid
        return {
            name: _normalize((workspace / rel).read_text(encoding="utf-8"), pid)
            for name, rel in ARTIFACTS.items()
        }
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmp, ignore_errors=True)


class GoldenArtifactTests(unittest.TestCase):
    def _run_language(self, language: str) -> None:
        scenario = SCENARIOS[language]
        # Pin json-hybrid so the golden is identical with or without lancedb.
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            produced = _generate(scenario)
        for name, text in produced.items():
            golden_path = GOLDEN_DIR / language / name
            if UPDATE:
                golden_path.parent.mkdir(parents=True, exist_ok=True)
                golden_path.write_text(text, encoding="utf-8", newline="\n")
                continue
            self.assertTrue(
                golden_path.exists(),
                f"missing golden {golden_path}; create it with SENTINEL_UPDATE_GOLDEN=1",
            )
            expected = golden_path.read_text(encoding="utf-8")
            self.assertEqual(
                text,
                expected,
                f"{language}/{name} drifted from its golden. If the change is intended, "
                f"regenerate with SENTINEL_UPDATE_GOLDEN=1 and review the git diff.",
            )

    def test_english_artifacts_match_golden(self):
        self._run_language("en")

    def test_spanish_artifacts_match_golden(self):
        self._run_language("es")


if __name__ == "__main__":
    unittest.main()
