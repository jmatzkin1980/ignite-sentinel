"""IMP-384: a change gap closes by citing the baseline (`by_baseline`), only with a verified literal quote."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.changes import change_gaps_path, get_change, validate_baseline_citation  # noqa: E402
from sentinel.gap_resolution import closure_for  # noqa: E402
from sentinel.gaps import CLOSURE_REASONS, parse_gap_rows  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCOPE_ANSWER = "\n".join([
    "### GAP-SCOPE",
    "- Respuesta: Sólo el formulario de alta de proveedores.",
    "- Borde:",
    '  - nuevo | pantalla | Botón "Guardar borrador" en el alta de proveedores',
    "  - adyacente | endpoint | Envío actual del alta de proveedores",
    "  - preservado | proceso | Envío completo del alta",
    "- Owner / fuente: Jefa de Compras",
    "- Estado de decisión: confirmado",
    "",
])
SAD = "00_raw/02_technology_context/sad-compras.md"
SAD_TEXT = (
    "# SAD Compras\n\nEl servicio de compras responde en menos de\n   dos segundos al percentil 95 en horario pico.\n"
    "Los datos se retienen durante siete años.\n"
)
QUOTE = "responde en menos de dos segundos al percentil 95"


def answer(evidence: str, status: str = "confirmado", closure: str = "by_baseline", gap: str = "GAP-TECH-NFR") -> str:
    return "\n".join([
        f"### {gap}",
        "- Respuesta: El servicio mantiene el requisito no funcional vigente de la línea de base.",
        "- Owner / fuente: Arquitectura",
        f"- Evidencia o referencia: {evidence}",
        f"- Estado de decisión: {status}",
        f"- Motivo de cierre: {closure}",
        "",
    ])


def cite(path: str = SAD, quote: str = QUOTE) -> str:
    return f'`{path}` "{quote}"'


class Base(SnapshotWorkspaceCase):
    project = "BAS"

    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", cls.project])
        run_ok(["ingest", cls.project, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", cls.project, "--source", "scope.md", "--change", "CHG-001"])

    def put(self, rel: str, data) -> None:
        path = workspace_path(self.project) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))

    def resolve_and_row(self, gap: str, text: str) -> dict:
        self.put(SAD, SAD_TEXT)
        Path("resp.md").write_text(text, encoding="utf-8")
        out = json.loads(run_ok(["resolve-gaps", self.project, "--source", "resp.md", "--change", "CHG-001"]))
        self.findings = out["closure_findings"]
        rows = parse_gap_rows(change_gaps_path(workspace_path(self.project), "CHG-001").read_text(encoding="utf-8"))
        return next(r for r in rows if r["id"] == gap)

    def assertStays(self, row: dict, needle: str = "") -> None:
        self.assertEqual(row["status"], "ANSWERED")
        self.assertNotEqual(row.get("closure_reason"), "by_baseline")
        self.assertTrue(any(needle in f for f in self.findings), self.findings)


class ByBaseline(Base):
    def test_valid_citation_closes_with_by_baseline(self):
        row = self.resolve_and_row("GAP-TECH-NFR", answer(cite()))
        self.assertEqual(row["status"], "CLOSED")
        self.assertEqual(row["closure_reason"], "by_baseline")

    def test_quote_not_verbatim_stays_answered(self):
        row = self.resolve_and_row("GAP-TECH-NFR", answer(cite(quote="responde en menos de dos segundos al percentil noventa")))
        self.assertStays(row, "literal")

    def test_quote_across_lines_and_spaces_closes(self):
        row = self.resolve_and_row("GAP-TECH-NFR", answer(cite(quote="menos   de   dos segundos   al percentil 95")))
        self.assertEqual(row["status"], "CLOSED")

    def test_typographic_quotes_close(self):
        row = self.resolve_and_row("GAP-TECH-NFR", answer(f"`{SAD}` “{QUOTE}”"))
        self.assertEqual(row["status"], "CLOSED")

    def test_different_case_stays_answered(self):
        row = self.resolve_and_row("GAP-TECH-NFR", answer(cite(quote=QUOTE.upper())))
        self.assertStays(row, "literal")

    def test_path_outside_00_raw_or_escaping_stays_answered(self):
        for path in ("state.json", "00_raw/../state.json", "../state.json", str(workspace_path(self.project) / "state.json")):
            with self.subTest(path=path):
                row = self.resolve_and_row("GAP-TECH-NFR", answer(cite(path, "state of the project is recorded here")))
                self.assertStays(row, "00_raw")

    def test_citing_a_change_note_stays_answered(self):
        note = get_change(self.project, "CHG-001")["source"]
        self.put(note, SAD_TEXT)  # even when the note carries the quote
        row = self.resolve_and_row("GAP-TECH-NFR", answer(cite(note)))
        self.assertStays(row, "nota de un cambio")

    def test_binary_or_non_utf8_file_stays_answered(self):
        for name, data in (("bin.md", b"\x00\x01" + SAD_TEXT.encode() + b"\x00"), ("latin.md", SAD_TEXT.encode() + "ñ".encode("latin-1"))):
            with self.subTest(name=name):
                self.put(f"00_raw/{name}", data)
                row = self.resolve_and_row("GAP-TECH-NFR", answer(cite(f"00_raw/{name}")))
                self.assertStays(row, "")

    def test_missing_file_and_missing_parts_stay_answered(self):
        for evidence in (cite("00_raw/no-existe.md"), f"`{SAD}`", f'"{QUOTE}"', "ver el SAD"):
            with self.subTest(evidence=evidence):
                row = self.resolve_and_row("GAP-TECH-NFR", answer(evidence))
                self.assertStays(row, "")

    def test_short_quote_stays_answered(self):
        row = self.resolve_and_row("GAP-TECH-NFR", answer(cite(quote="siete años")))
        self.assertStays(row, "20")

    def test_unconfirmed_answer_does_not_close(self):
        row = self.resolve_and_row("GAP-TECH-NFR", answer(cite(), status="pendiente"))
        self.assertNotEqual(row["status"], "CLOSED")

    def test_validator_returns_none_or_text(self):
        self.put(SAD, SAD_TEXT)
        base = workspace_path(self.project)
        self.assertIsNone(validate_baseline_citation(base, self.project, "CHG-001", cite()))
        self.assertIsInstance(validate_baseline_citation(base, self.project, "CHG-001", "nada"), str)


class ScopeByBaseline(Base):
    project = "BSC"

    def snapshot(self) -> tuple:
        base = workspace_path(self.project)
        folder = base / "07_changes" / "00_client_responses"
        copies = sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []
        return (copies, (base / "state.json").read_bytes(), change_gaps_path(base, "CHG-001").read_bytes())

    def test_scope_by_baseline_without_border_is_rejected_before_any_write(self):
        # a change whose scope is still open: build a fresh one in this class
        self.put(SAD, SAD_TEXT)
        base = workspace_path(self.project)
        text = chr(10).join([
            "### GAP-SCOPE",
            "- Respuesta: Sólo el formulario de alta de proveedores.",
            "- Owner / fuente: Jefa de Compras",
            f"- Evidencia o referencia: {cite()}",
            "- Estado de decisión: confirmado",
            "- Motivo de cierre: by_baseline",
            "",
        ])
        Path("resp.md").write_text(text, encoding="utf-8")
        before = self.snapshot()
        code, _ = __import__("helpers").run_cli(["resolve-gaps", self.project, "--source", "resp.md", "--change", "CHG-001"])
        self.assertNotEqual(code, 0)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(base.exists())

    def test_failing_citation_alone_stays_answered_and_never_raises(self):
        row = self.resolve_and_row("GAP-TECH-NFR", answer(cite(quote="no está en el archivo de ninguna manera")))
        self.assertStays(row, "literal")


class ProjectPath(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "proyecto.md")
        run_ok(["init", "PRJ"])
        run_ok(["ingest", "PRJ", "--source", "proyecto.md"])

    def respond(self, closure: str):
        base = workspace_path("PRJ")
        (base / SAD).parent.mkdir(parents=True, exist_ok=True)
        (base / SAD).write_text(SAD_TEXT, encoding="utf-8")
        Path("resp.md").write_text(answer(cite(), closure=closure, gap="GAP-OBJECTIVE"), encoding="utf-8")
        out = json.loads(run_ok(["resolve-gaps", "PRJ", "--source", "resp.md"]))
        rows = parse_gap_rows((base / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        return next(r for r in rows if r["id"] == "GAP-OBJECTIVE"), out["closure_findings"]

    def test_project_path_by_baseline_does_not_close(self):
        row, findings = self.respond("by_baseline")
        self.assertEqual(row["status"], "ANSWERED")
        self.assertTrue(any("sólo vale en un cambio" in f for f in findings), findings)

    def test_project_path_unknown_reason_message_unchanged(self):
        self.assertNotIn("by_baseline", CLOSURE_REASONS)
        _, findings = closure_for("GAP-X", {"closure": "nonsense", "evidence": "x"}, "confirmed")
        self.assertEqual(findings, [f"GAP-X: unknown closure reason 'nonsense'; use one of {', '.join(CLOSURE_REASONS)}."])


class GuideShowsExample(unittest.TestCase):
    def test_change_guide_has_by_baseline_example(self):
        from sentinel.gaps.render import change_border_guide

        for language in ("es", "en"):
            self.assertIn("by_baseline", change_border_guide(language))


if __name__ == "__main__":
    unittest.main()
