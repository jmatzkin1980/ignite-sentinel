"""IMP-175: golden/snapshot tests for the generated artifacts in English AND
Spanish. Covered: discovery gaps, project brief, PRD, specs, backlog, a quality
test case (TC-001) + the backlog readiness audit, and the traceability matrix.

IMP-215 (H10, F-GOLD-1/2/3) added gaps/quality/trace-matrix coverage. IMP-219
(H11, F-GOLD-4/5) closes the last two deferred surface classes on the same
populated fixture: the `/trace` *mermaid graph* snapshot and the human-facing
projections `/view` HTML (5 artifacts) + `/export` mdx/interview/faq. Their
timestamped, path-bearing, JS-carrying output is stabilized through the shared
conservative normalization harness in ``tests/golden_normalize.py`` (project id,
absolute workspace paths, ISO timestamps, bare dates, sha256 hashes -> stable
placeholders); nothing else is masked, so a dropped section still breaks the golden.

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
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.memory import ContextBroker

# `discover -s tests` puts this dir on sys.path; add it explicitly so the sibling
# harness also resolves when the module is run directly (e.g. `-m unittest
# tests.test_golden_artifacts`).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_normalize import normalize  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"
UPDATE = os.environ.get("SENTINEL_UPDATE_GOLDEN") == "1"

ARTIFACTS = {
    "gaps.md": "01_discovery/gaps.md",
    "project-brief.md": "02_requirements/project-brief.md",
    "prd.md": "03_specs/prd.md",
    "specs.md": "03_specs/specs.md",
    "backlog.md": "04_backlog/BACKLOG.md",
    "test-case.md": "05_quality/TC-001.md",
    "quality-audit.md": "05_quality/backlog_readiness_audit.md",
    "trace-matrix.md": "06_traceability/traceability_matrix.md",
    # IMP-219: the `/trace` mermaid graph, written next to the matrix by the same
    # `trace` command run below.
    "trace-graph.md": "06_traceability/traceability_graph.md",
}

# IMP-219: human-facing `/view` HTML surfaces snapshotted over the same populated
# workspace. Each artifact key is a supported `/view --artifact` value.
VIEW_ARTIFACTS = ("gaps", "brief", "prd", "specs", "backlog")

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


def _generate(scenario: dict) -> dict[str, str]:
    from sentinel.cli import main
    from sentinel.export import export_artifact
    from sentinel.view import generate_artifact_view

    pid = scenario["project_id"]
    old_cwd = Path.cwd()
    tmp = Path(tempfile.mkdtemp())
    os.chdir(tmp)
    try:
        raw = tmp / "raw.md"
        raw.write_text(scenario["raw"], encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            if main(["init", pid, "--brief-version", "1"]) != 0:
                raise AssertionError("init failed")
            if main(["ingest", pid, "--source", str(raw)]) != 0:
                raise AssertionError("ingest failed")
            for index, statement in enumerate(scenario["ears"], start=1):
                answer = tmp / f"answer-{index}.md"
                answer.write_text(scenario["answer"].format(s=statement, i=index), encoding="utf-8")
                if main(["resolve-gaps", pid, "--source", str(answer)]) != 0:
                    raise AssertionError(f"resolve-gaps {index} failed")
            for command in ("brief", "specs", "backlog", "quality", "trace"):
                if main([command, pid]) != 0:
                    raise AssertionError(f"{command} failed")
            # IMP-219: human-facing projections over the now-mature workspace.
            for view_artifact in VIEW_ARTIFACTS:
                generate_artifact_view(pid, view_artifact)
            # IMP-247: the build-readiness view (its own model, not a Markdown artifact).
            generate_artifact_view(pid, "readiness")
            export_artifact(pid, "prd", "mdx")
            export_artifact(pid, "gaps", "interview")
            export_artifact(pid, "gaps", "faq")
        workspace = tmp / "workspaces" / pid
        produced = {
            name: normalize((workspace / rel).read_text(encoding="utf-8"), pid)
            for name, rel in ARTIFACTS.items()
        }
        views = workspace / "08_context_packs" / "views"
        roots = {str(tmp.resolve()), tmp.resolve().as_posix(), str(tmp), tmp.as_posix()}
        for view_artifact in VIEW_ARTIFACTS + ("readiness",):
            html = (views / f"{view_artifact}.html").read_text(encoding="utf-8")
            # IMP-240: checked on the RAW page; normalize() would hide the prefix.
            leaked = [root for root in roots if root and root in html]
            if leaked:
                raise AssertionError(f"view/{view_artifact}.html embeds the absolute workspace root: {leaked[0]}")
            produced[f"view/{view_artifact}.html"] = normalize(html, pid)
        exports = workspace / "08_context_packs" / "exports"
        produced["export/prd.mdx"] = normalize(
            (exports / "prd-mdx" / "index.mdx").read_text(encoding="utf-8"), pid
        )
        produced["export/gaps-interview.md"] = normalize(
            (exports / "gaps-interview.md").read_text(encoding="utf-8"), pid
        )
        produced["export/gaps-faq.md"] = normalize(
            (exports / "gaps-faq.md").read_text(encoding="utf-8"), pid
        )
        return produced
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmp, ignore_errors=True)


class GoldenArtifactTests(unittest.TestCase):
    def _run_language(self, language: str) -> None:
        scenario = SCENARIOS[language]
        # Pin json-hybrid so the golden is identical with or without lancedb.
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            produced = _generate(scenario)
        self._check_view_export_contract(language, produced)
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

    def _check_view_export_contract(self, language: str, produced: dict[str, str]) -> None:
        """IMP-240: the feedback export reads exactly the same model fields as before.

        `view_export_projection.json` was frozen from the pre-IMP-240 goldens; the
        JS export functions are unchanged, so an identical projection means an
        identical export.
        """
        from test_view_shell import embedded_view_model, export_projection

        frozen = json.loads((GOLDEN_DIR / "view_export_projection.json").read_text(encoding="utf-8"))
        for artifact in VIEW_ARTIFACTS:
            model = embedded_view_model(produced[f"view/{artifact}.html"])
            with self.subTest(language=language, artifact=artifact):
                self.assertEqual(export_projection(model), frozen[f"{language}/{artifact}"])

    def test_view_goldens_stay_within_size_budget(self):
        """IMP-240: deduplicating the embedded model keeps the 10 view goldens <= 2.1 MB."""
        total = sum(path.stat().st_size for path in GOLDEN_DIR.glob("*/view/*.html"))
        self.assertLessEqual(total, 2_100_000, f"view goldens weigh {total} bytes")

    def test_view_goldens_embed_no_absolute_paths(self):
        import re

        for path in GOLDEN_DIR.glob("*/view/*.html"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(view=str(path.relative_to(GOLDEN_DIR))):
                self.assertIsNone(re.search(r'"[A-Za-z]:[\/]|/Users/|/home/|\\Users', text))

    def test_english_artifacts_match_golden(self):
        self._run_language("en")

    def test_spanish_artifacts_match_golden(self):
        self._run_language("es")


if __name__ == "__main__":
    unittest.main()
