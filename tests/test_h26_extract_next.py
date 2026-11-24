"""IMP-402 (H26 inc 3) task 7: `/next --change` walks the extraction and the preserved surfaces before the brief."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, complete_extraction, export_final_brief, run_ok, waive_coherence, waive_crosses  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402
from test_change_next import load_baseline, set_change  # noqa: E402
from test_change_specs import ALL_ANSWERS, answer  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.extraction.confirm import confirm_item, confirm_proposals  # noqa: E402
from sentinel.extraction.inventory import build_inventory, element_lines, element_text, load_inventory  # noqa: E402
from sentinel.extraction.proposals import record_proposals  # noqa: E402
from sentinel.readiness_verdict import CHANGE_COMMANDS, CHANGE_TEXT, change_next_step  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CID = "CHG-001"
HOME_SECTION = {2: "objetivo", 3: "alcance", 4: "proceso", 6: "preservado", 7: "reglas"}


def all_as_sections(project: str, flagged: str | None = None) -> str:
    base = workspace_path(project)
    blocks = []
    for element in load_inventory(base, CID)["elements"]:
        quote = " ".join((element_text(base, element) or "").split())[:60].strip()
        first, last = element_lines(element)
        lines = [f"### {element['id']}", "- Tratamiento: seccion", f"- Líneas: {first}-{last}", f"- Seccion: {HOME_SECTION.get(element['home'], 'reglas')}",
                 f'- Cita: "{quote}"']
        if element["id"] == flagged:
            lines.append("- Marca: sin_respaldo — sin respaldo en la línea de base")
        blocks.append("\n".join(lines) + "\n")
    return "\n".join(blocks)


def submit(project: str, text: str) -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "p.md"
        path.write_text(text, encoding="utf-8")
        result = record_proposals(project, CID, path)
    assert not result["rejected"], result


class MatureNext(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_mature" / "pedido_maduro.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "MAD"])
        run_ok(["ingest", "MAD", "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", "MAD", "--source", "scope.md", "--change", CID])
        waive_crosses("MAD", CID)
        load_baseline("MAD")

    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def test_after_lenses_comes_inventory(self):
        s = change_next_step("MAD", CID)
        self.assertEqual(s["key"], "extract_inventory")
        self.assertEqual(s["command"], f"/extract MAD --change {CID}")
        self.assertEqual(s["title"], "Inventariar el pedido")

    def test_proposals_then_confirm_then_preserved(self):
        build_inventory("MAD", CID)
        s = change_next_step("MAD", CID)
        self.assertEqual(s["key"], "extract_proposals")
        self.assertIn("13 de 13", s["text"])
        self.assertEqual(s["command"], f"/extract MAD --change {CID} --proposals PATH")
        submit("MAD", all_as_sections("MAD", flagged="Regla 2"))
        s = change_next_step("MAD", CID)
        self.assertEqual(s["key"], "extract_confirm")
        self.assertIn("1 marcada(s)", s["text"])
        self.assertEqual(s["command"], f"/extract MAD --change {CID} --confirm all")
        confirm_proposals("MAD", CID, "all")
        confirm_item("MAD", CID, "Regla 2")
        s = change_next_step("MAD", CID)
        self.assertEqual(s["key"], "preserved")
        self.assertIn("Envío completo del alta", s["text"])
        self.assertEqual(s["command"], f"/extract MAD --change {CID} --proposals PATH")

    def test_stale_inventory_step(self):
        build_inventory("MAD", CID)
        pedido = workspace_path("MAD").parent / "otro_pedido.md"
        pedido.write_text("# Otro pedido\n\n- Regla 1: algo distinto que el inventario no conoce todavía.\n", encoding="utf-8")
        run_ok(["sources", "MAD", "--load", str(pedido), "--role", "pedido", "--change", CID])
        waive_crosses("MAD", CID)  # a new request source makes the waived cross-reads stale (IMP-404)
        s = change_next_step("MAD", CID)
        self.assertEqual(s["key"], "extract_inventory")
        self.assertEqual(s["title"], "Reinventariar el pedido")

    def test_requirements_none_points_to_extract(self):
        complete_extraction("MAD", CID)
        self.assertEqual(change_next_step("MAD", CID)["key"], "brief")
        run_ok(["brief", "MAD", "--change", CID])
        s = change_next_step("MAD", CID)
        self.assertEqual(s["key"], "requirements")
        self.assertEqual(s["title"], "Proponer los requisitos del cambio")
        self.assertEqual(s["command"], f"/extract MAD --change {CID} --proposals PATH")

    def test_english_texts(self):
        set_change("MAD", language="en")
        waive_coherence("MAD", CID)  # the lens view is written in the language of the change
        build_inventory("MAD", CID)
        s = change_next_step("MAD", CID)
        self.assertEqual(s["key"], "extract_proposals")
        self.assertIn("of 13 request elements", s["text"])


class BorradorDone(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", CID])
        load_baseline("BORR")

    def walk(self) -> None:
        forget_read_snapshots()
        answer("BORR", CID, "a.md", ALL_ANSWERS)
        complete_extraction("BORR", CID)
        run_ok(["brief", "BORR", "--change", CID])
        export_final_brief("BORR", CID)
        for command in ("specs", "backlog", "validate"):
            run_ok([command, "BORR", "--change", CID])

    def test_done_says_coverage(self):
        self.walk()
        s = change_next_step("BORR", CID)
        self.assertEqual(s["key"], "done")
        self.assertIn("1 de 1", s["text"])
        self.assertEqual(s["command"], "")

    def test_english_done(self):
        self.walk()
        set_change("BORR", language="en")
        waive_coherence("BORR", CID)  # the lens view is written in the language of the change
        self.assertIn("The extraction covers", change_next_step("BORR", CID)["text"])


    def preserved_step(self, ears_gaps):
        from sentinel.extraction.coverage import extraction_coverage as real

        def empty(*args, **kwargs):
            return {**real(*args, **kwargs), "total": 0}

        with patch("sentinel.readiness_verdict._change_step_key", return_value="preserved"),                 patch("sentinel.extraction.coverage.extraction_coverage", side_effect=empty),                 patch("sentinel.readiness_verdict._open_ears_gaps", return_value=ears_gaps),                 patch("sentinel.extraction.coverage.preserved_coverage", return_value={"missing": ["Alta"]}):
            return change_next_step("BORR", CID)

    def test_preserved_without_elements_or_questions_points_to_a_request_source(self):
        step = self.preserved_step([])
        self.assertEqual(step["command"], f"/sources BORR --load PATH --role pedido --change {CID}")
        self.assertNotIn("GAP-ACCEPTANCE", step["text"])
        step = self.preserved_step(["GAP-BUSINESS-RULES"])
        self.assertIn("GAP-BUSINESS-RULES", step["text"])
        self.assertEqual(step["command"], f"/resolve-gaps BORR --source PATH --change {CID}")


class Keys(unittest.TestCase):
    def test_step_keys(self):
        self.assertEqual(set(CHANGE_COMMANDS), {
            "scope", "baseline", "lenses", "crosses", "cross_new_surfaces", "coherence", "coherence_view", "extract_inventory", "extract_unreadable", "extract_proposals", "extract_confirm",
            "extract_confirm_flagged", "extract_partial", "extract_orphans", "preserved", "preserved_answer", "preserved_source",
            "brief", "requirements", "export_final", "export_not_ready", "extract_verify", "extract_verify_result", "specs", "backlog", "validate", "done"})
        for language in ("es", "en"):
            self.assertNotIn("pending_extraction", CHANGE_TEXT[language])


if __name__ == "__main__":
    unittest.main()
