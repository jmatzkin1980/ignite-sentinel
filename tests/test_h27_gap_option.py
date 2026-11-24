"""IMP-408 (H27 inc 2) task 1: the `Opción:` field and the refusal of a confirmed answer that names several options."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402
from test_h26_cross_record import CID, PID, CrossCase  # noqa: E402

from sentinel.changes import change_gaps_path  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.gap_resolution import apply_gap_responses  # noqa: E402
from sentinel.gaps import parse_gap_responses  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

DIS_ID = "GAP-DIS-0A1B2C3D"
DIS = {"id": DIS_ID, "lens": "design", "severity": "high", "status": "OPEN",
       "question": "¿Qué rige? Opciones: (A) rige el diseño; (B) rige el pedido; (C) se corrigen los dos.",
       "description": "x"}
THREE = "(A) rige el diseño. (B) rige el pedido. (C) se corrigen los dos."
SEVERAL_ES = ("la respuesta confirmada nombra varias opciones (A, B, C); "
              "elegí una opción en `Opción:` (una de A, B, C)")
SEVERAL_EN = ("the confirmed answer names several options (A, B, C); "
              "choose one option in `Option:` (one of A, B, C)")


def respond(gap_id: str, answer: str, option: str = "", language: str = "es") -> dict:
    labels = {"es": ("Respuesta", "Opción", "Estado de decisión", "confirmado", "Evidencia o referencia"),
              "en": ("Answer", "Option", "Decision status", "confirmed", "Evidence or reference")}[language]
    lines = [f"### {gap_id}", f"- {labels[0]}: {answer}"]
    if option:
        lines.append(f"- {labels[1]}: {option}")
    lines += [f"- {labels[2]}: {labels[3]}", f"- {labels[4]}: F-03:12"]
    return parse_gap_responses("\n".join(lines) + "\n")


class Parsing(unittest.TestCase):
    def test_parser_reads_option(self):
        self.assertEqual(respond(DIS_ID, THREE, "B")[DIS_ID]["option"], "B")
        self.assertEqual(respond(DIS_ID, THREE, "C", language="en")[DIS_ID]["option"], "C")
        self.assertNotIn("option", respond(DIS_ID, THREE)[DIS_ID])


class Applying(unittest.TestCase):
    def apply(self, answer: str, option: str = "", language: str = "es", gap: dict = DIS):
        result = apply_gap_responses([gap], respond(gap["id"], answer, option, language), language=language)
        return result["gaps"][0], result

    def test_several_options_refused(self):
        gap, result = self.apply(THREE)
        self.assertEqual(gap["status"], "ANSWERED")
        self.assertEqual(gap["resolution_note"], SEVERAL_ES)
        self.assertIn(f"{DIS_ID}: {SEVERAL_ES}", result["findings"])
        gap, _ = self.apply(THREE, language="en")
        self.assertEqual(gap["resolution_note"], SEVERAL_EN)

    def test_option_field_closes(self):
        gap, _ = self.apply(THREE, "B")
        self.assertEqual(gap["status"], "CLOSED")
        self.assertEqual(gap["option"], "B")

    def test_option_field_wins_over_markers(self):
        gap, _ = self.apply("Rige el pedido; el prototipo muestra (A) por error.", "B")
        self.assertEqual(gap["status"], "CLOSED")
        self.assertEqual(gap["option"], "B")

    def test_option_loose_forms(self):
        for raw in ("(b)", "B — rige el pedido", "b"):
            gap, _ = self.apply(THREE, raw)
            self.assertEqual(gap["option"], "B", raw)
        gap, _ = self.apply(THREE, "b", language="en")
        self.assertEqual(gap["option"], "B")

    def test_option_field_with_several_letters_refused(self):
        for raw in ("A y B", "A/B", "B, C"):
            gap, _ = self.apply(THREE, raw)
            self.assertEqual(gap["status"], "ANSWERED", raw)
            self.assertEqual(gap.get("option", ""), "", raw)
            self.assertIn("nombra varias opciones", gap["resolution_note"], raw)
        gap, _ = self.apply(THREE, "A and B", language="en")
        self.assertEqual(gap["status"], "ANSWERED")
        self.assertIn("names several options (A, B)", gap["resolution_note"])
        gap, _ = self.apply(THREE, "B — se corrige a favor del pedido")
        self.assertEqual((gap["status"], gap["option"]), ("CLOSED", "B"))

    def test_unknown_option_refused(self):
        gap, _ = self.apply(THREE, "E")
        self.assertEqual(gap["status"], "ANSWERED")
        self.assertEqual(gap["resolution_note"], "`Opción: E` no es una de las opciones (A, B, C); elegí una en `Opción:`")

    def test_prose_and_single_marker_close(self):
        gap, _ = self.apply("Rige el pedido: el umbral es 5.000.000 y el prototipo se corrige.")
        self.assertEqual((gap["status"], gap["option"]), ("CLOSED", ""))
        gap, _ = self.apply("(B) rige el pedido: el umbral es 5.000.000.")
        self.assertEqual((gap["status"], gap["option"]), ("CLOSED", "B"))

    def test_candidate_options_of_a_project_gap(self):
        gap = {"id": "GAP-DESIGN-STATES", "lens": "design", "severity": "medium", "status": "OPEN",
               "evidence_mention": "dashboard", "description": "x"}
        responses = parse_gap_responses(
            "### GAP-DESIGN-STATES\n- Answer: Option A for the dashboard states and Option B for scope.\n"
            "- Decision status: confirmed\n- Evidence or reference: F-03:12\n")
        result = apply_gap_responses([gap], responses, language="en")
        self.assertEqual(result["gaps"][0]["status"], "ANSWERED")
        self.assertEqual(result["gaps"][0]["resolution_note"],
                         "the confirmed answer names several options (A, B); choose one option in `Option:` (one of A, B)")

    def test_option_without_options_is_ignored(self):
        gap = {"id": "GAP-OBJECTIVE", "lens": "business", "severity": "high", "status": "OPEN", "description": "x"}
        responses = respond("GAP-OBJECTIVE", "Reducir el tiempo de alta de proveedores de cinco días a dos.", "A")
        result = apply_gap_responses([gap], responses, language="es")
        self.assertEqual(result["gaps"][0]["status"], "CLOSED")
        self.assertIn("GAP-OBJECTIVE: Opción se ignora: la pregunta no tiene opciones", result["findings"])


class OnAChange(CrossCase):
    def answers(self, dis_id: str, option: str = "") -> Path:
        lines = [f"### {dis_id}", f"- Respuesta: {THREE}"]
        if option:
            lines.append(f"- Opción: {option}")
        lines += ["- Estado de decisión: confirmado", f"- Evidencia o referencia: {self.ids()['pedido']}:1"]
        path = Path.cwd() / f"resp-{len(list(Path.cwd().glob('resp-*')))}.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_cross_gap_on_a_change(self):
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        dis_id = next(i for i in self.gaps() if i.startswith("GAP-DIS-"))
        text = change_gaps_path(workspace_path(PID), CID).read_text(encoding="utf-8")
        self.assertIn("- Opción:", text.split(f"### {dis_id}")[1].split("### ")[0])
        out = run_ok(["resolve-gaps", PID, "--source", str(self.answers(dis_id)), "--change", CID])
        several = json.loads(out)
        self.assertIn(dis_id, several["answered"])
        self.assertTrue(any("elegí una opción en `Opción:`" in item for item in several["closure_findings"]))
        out = run_ok(["resolve-gaps", PID, "--source", str(self.answers(dis_id, "B")), "--change", CID])
        chosen = json.loads(out)
        self.assertIn(dis_id, chosen["closed"])
        self.assertEqual(chosen["options"], {dis_id: "B"})
        report = Path(chosen["path"])
        report = report if report.is_absolute() else Path.cwd() / report
        self.assertIn("_(option B)_", report.read_text(encoding="utf-8"))


class ProjectPath(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        run_ok(["init", "OPTP"])
        run_ok(["ingest", "OPTP", "--source", str(Path(__file__).resolve().parent / "fixtures" / "incomplete_requirement.md")])

    def test_project_gaps_md_unchanged(self):
        text = (workspace_path("OPTP") / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertNotIn("- Option:", text)
        self.assertNotIn("- Opción:", text)


if __name__ == "__main__":
    unittest.main()
