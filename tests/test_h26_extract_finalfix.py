"""IMP-402 (H26 inc 3) final review fixes: orphans, unchanged re-submissions, unreadable requests, held steps."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import complete_extraction, run_ok, waive_crosses  # noqa: E402
from test_h26_extract_proposals import CID, EXAMPLE, PID, ProposalsCase  # noqa: E402

from sentinel.change_requirements import load_change_ears  # noqa: E402
from sentinel.changes import _request_states_acceptance, list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.discovery.detection import detect_gaps  # noqa: E402
from sentinel.errors import GateRefusal  # noqa: E402
from sentinel.extraction import extraction_dir, run_extract  # noqa: E402
from sentinel.extraction.confirm import confirm_proposals, reject_item  # noqa: E402
from sentinel.extraction.coverage import extraction_coverage, extraction_view  # noqa: E402
from sentinel.extraction.flags import element_flags  # noqa: E402
from sentinel.extraction.inventory import build_inventory, inventory_state, load_inventory  # noqa: E402
from sentinel.extraction.proposals import load_proposals, parse_proposals, record_proposals  # noqa: E402
from sentinel.readiness_verdict import change_next_step  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

HEADING_ONLY = (
    "# Pedido\n\n## Objetivo\nQue el alta de proveedores quede registrada en el sistema.\n\n"
    "## Criterios de aceptación\n- Dado un alta completa, cuando el analista la envía, entonces queda pendiente.\n"
)


def pedido_path() -> Path:
    inventory = load_inventory(workspace_path(PID), CID)
    path = Path(inventory["sources"][0]["path"])
    return path if path.is_absolute() else Path.cwd() / path


def set_language(language: str) -> None:
    changes = {key: dict(value) for key, value in list_changes(PID).items()}
    changes[CID]["language"] = language
    update_state(PID, changes=changes)


class Finalfix(ProposalsCase):
    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def waive_baseline(self) -> None:
        run_ok(["sources", PID, "--change", CID, "--no-baseline", "--reason", "Sistema nuevo"])
        waive_crosses(PID, CID)

    # item 2: orphans
    def test_orphan_rows_step_and_reject(self):
        self.waive_baseline()
        complete_extraction(PID, CID)
        self.assertEqual(change_next_step(PID, CID)["key"], "brief")
        rows = [r["id"] for r in load_change_ears(PID, CID) if "EXT:SEC-objetivo" in r["source"]]
        self.assertTrue(rows)
        path = pedido_path()
        text = path.read_text(encoding="utf-8")
        start = text.index("## Objetivo")
        path.write_text(text[:start] + text[text.index("## Usuarios"):], encoding="utf-8")
        result = run_extract(PID, CID)
        self.assertEqual(result["coverage"]["orphans"], [{"id": "SEC-objetivo", "rows": rows}])
        self.assertFalse(result["coverage"]["complete"])
        step = result["next_step"]
        self.assertEqual(step["key"], "extract_orphans")
        self.assertEqual(step["command"], f'/extract {PID} --change {CID} --reject-item SEC-objetivo --reason "..."')
        self.assertIn("SEC-objetivo", step["text"])
        review = (extraction_dir(workspace_path(PID), CID) / "review.md").read_text(encoding="utf-8")
        self.assertIn("Huérfanas", review)
        self.assertIn("SEC-objetivo", review.split("Huérfanas", 1)[1])
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertIn("extraction_orphans", json.dumps(status))
        set_language("en")
        self.assertEqual(change_next_step(PID, CID)["title"], "Take out the orphan elements")
        set_language("es")

        result = reject_item(PID, CID, "SEC-objetivo", "el pedido ya no lo trae")
        self.assertEqual(sorted(result["rows_superseded"]), sorted(rows))
        self.assertFalse([r for r in load_change_ears(PID, CID) if "EXT:SEC-objetivo" in r["source"]])
        self.assertEqual(extraction_coverage(PID, CID)["orphans"], [])
        self.assertTrue(extraction_coverage(PID, CID)["complete"])
        self.assertNotEqual(change_next_step(PID, CID)["key"], "extract_orphans")

    # item 3: a re-submission equal to a confirmed item keeps it confirmed
    def test_resubmission_keeps_confirmed_items(self):
        record_proposals(PID, CID, EXAMPLE)
        confirm_proposals(PID, CID, "all")
        corrected = EXAMPLE.read_text(encoding="utf-8").replace(
            "es una exclusión de alcance y ya está en la respuesta de GAP-SCOPE", "el borde ya lo excluye")
        self.assertNotEqual(corrected, EXAMPLE.read_text(encoding="utf-8"))
        again = Path.cwd() / "again.md"
        again.write_text(corrected, encoding="utf-8")
        result = run_extract(PID, CID, proposals=str(again))
        self.assertEqual(result["unchanged"], ["HU-01", "RN-02", "SEC-objetivo"])
        self.assertEqual(result["recorded"], ["RN-04", "RN-06"])
        items = load_proposals(workspace_path(PID), CID)["items"]
        self.assertEqual({i: items[i]["status"] for i in ("HU-01", "RN-02", "SEC-objetivo", "RN-06")},
                         {"HU-01": "confirmed", "RN-02": "confirmed", "SEC-objetivo": "confirmed", "RN-06": "proposed"})
        self.assertIn("3 sin cambios (siguen confirmadas)", result["message"])

    # item 4: unreadable request, then an empty but readable one
    def test_unreadable_request_is_not_complete(self):
        self.waive_baseline()
        pedido_path().write_bytes(b"\x00\x01\x02 binario")
        build_inventory(PID, CID)
        cover = extraction_coverage(PID, CID)
        self.assertEqual((cover["state"], cover["total"], cover["unreadable"]), ("empty", 0, ["F-01"]))
        self.assertFalse(cover["complete"])
        step = change_next_step(PID, CID)
        self.assertEqual(step["key"], "extract_unreadable")
        self.assertEqual(step["command"], f"/sources {PID} --load PATH --role pedido --change {CID}")
        self.assertIn("--superseded-by", step["text"])
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertIn("extraction_unreadable", json.dumps(status))
        # the way out: load a readable copy and mark the unreadable one as superseded
        readable = Path.cwd() / "pedido-legible.md"
        readable.write_text("## Reglas\n- RN-01: El CUIT del proveedor debe ser único en el padrón.\n", encoding="utf-8")
        run_ok(["sources", PID, "--load", str(readable), "--role", "pedido", "--change", CID])
        run_ok(["sources", PID, "--id", "F-01", "--superseded-by", "F-02", "--reason", "copia ilegible"])
        waive_crosses(PID, CID)  # a new request source makes the waived cross-reads stale (IMP-404)
        build_inventory(PID, CID)
        cover = extraction_coverage(PID, CID)
        self.assertEqual((cover["unreadable"], cover["total"]), ([], 1))
        self.assertEqual(change_next_step(PID, CID)["key"], "extract_proposals")

    def test_empty_readable_request_points_preserved_to_an_answer(self):
        self.waive_baseline()
        pedido_path().write_text("# Pedido sin cuerpo\n", encoding="utf-8")
        build_inventory(PID, CID)
        cover = extraction_coverage(PID, CID)
        self.assertEqual((cover["state"], cover["unreadable"], cover["complete"]), ("empty", [], True))
        step = change_next_step(PID, CID)
        self.assertEqual(step["key"], "preserved")
        # no EARS question is open here, so the way out is a request note loaded as a source (IMP-404 task 1)
        self.assertEqual(step["command"], f"/sources {PID} --load PATH --role pedido --change {CID}")
        self.assertNotIn("--proposals", step["text"])
        self.assertIn("UNCHANGED", step["text"])
        set_language("en")
        self.assertIn("The request brings no elements to quote", change_next_step(PID, CID)["text"])

    # item 5: the change's lens round reads an itemized acceptance heading or CA-/AC- ids
    def test_acceptance_signal_change_path_only(self):
        base = workspace_path(PID)
        note = Path.cwd() / "nota.md"
        for text, expected in (
            (HEADING_ONLY, True),
            ("## Reglas\n- CA-01: Dado un alta, cuando se envía, entonces queda pendiente.\n", True),
            ("## Objetivo\nQue el alta quede registrada.\n", False),
            ("## Criterios de priorización\n- Primero lo urgente.\n", False),
        ):
            note.write_text(text, encoding="utf-8")
            self.assertIs(_request_states_acceptance(base, {"source": str(note)}), expected, text)
        # the project path is untouched: the same text still opens GAP-ACCEPTANCE there
        self.assertIn("GAP-ACCEPTANCE", {gap["id"] for gap in detect_gaps(HEADING_ONLY)})

    # f: rows of an item that is no longer confirmed do not reach the brief
    def test_view_rows_only_of_confirmed_items(self):
        record_proposals(PID, CID, EXAMPLE)
        confirm_proposals(PID, CID, "all")
        self.assertIn("RN-02", extraction_view(PID, CID)["rows"])
        text = EXAMPLE.read_text(encoding="utf-8")
        rn02 = text[text.index("### RN-02"):text.index("### RN-04")]
        again = Path.cwd() / "rn02.md"
        again.write_text(rn02.replace("dejarla Pendiente de aprobación", "dejarla en espera de aprobación"), encoding="utf-8")
        self.assertEqual(record_proposals(PID, CID, again)["recorded"], ["RN-02"])
        self.assertTrue(load_change_ears(PID, CID))
        self.assertNotIn("RN-02", extraction_view(PID, CID)["rows"])

    # g: a section whose elements were all discarded says so
    def test_brief_section_with_every_element_discarded(self):
        discard = "\n".join([
            "### SEC-objetivo", "- Tratamiento: descarte", "- Motivo: se trata en otro cambio",
            '- Cita: "la jefatura aprueba las altas de monto alto dentro del sistema"',
            "### SEC-usuarios", "- Tratamiento: descarte", "- Motivo: se trata en otro cambio",
            '- Cita: "Analista de Compras: carga el alta del proveedor."', "",
        ])
        path = Path.cwd() / "descartes.md"
        path.write_text(discard, encoding="utf-8")
        self.assertEqual(record_proposals(PID, CID, path)["recorded"], ["SEC-objetivo", "SEC-usuarios"])
        confirm_proposals(PID, CID, "all")
        run_ok(["brief", PID, "--change", CID])
        brief = (workspace_path(PID) / "02_requirements" / CID / "project-brief.md").read_text(encoding="utf-8")
        lines = brief.splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("## 2."))
        end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
        section = "\n".join(lines[start:end])
        self.assertIn("se descartaron (SEC-objetivo, SEC-usuarios)", section)
        self.assertIn("§9", section)
        self.assertNotIn("no trae elementos", section)

    # minor: a flagged-only confirm step names --confirm-item, not --confirm all
    def test_confirm_step_when_only_flagged_left(self):
        cover = {"state": "current", "total": 3, "pending": 0, "proposed": 1, "flagged": 1, "flagged_ids": ["RN-04"],
                 "text": "2 de 3"}
        with patch("sentinel.readiness_verdict._change_step_key", return_value="extract_confirm"), \
                patch("sentinel.extraction.coverage.extraction_coverage", return_value=cover):
            step = change_next_step(PID, CID)
        self.assertEqual(step["command"], f"/extract {PID} --change {CID} --confirm-item RN-04")
        self.assertNotIn("--confirm all", step["text"])
        self.assertIn("RN-04", step["text"])
        self.assertIn("--reject-item", step["text"])

    # minor: confirming against a stale inventory is refused; rejecting is not
    def test_confirm_refuses_a_stale_inventory(self):
        record_proposals(PID, CID, EXAMPLE)
        second = Path.cwd() / "pedido-2.md"
        second.write_text("## Reglas\n- RN-07: Una regla nueva del segundo pedido del cambio.\n", encoding="utf-8")
        run_ok(["sources", PID, "--load", str(second), "--role", "pedido", "--change", CID])
        self.assertEqual(inventory_state(PID, CID), "stale")
        with self.assertRaises(GateRefusal) as caught:
            confirm_proposals(PID, CID, "all")
        self.assertIn("quedó viejo", str(caught.exception))
        self.assertEqual(reject_item(PID, CID, "HU-01", "no aplica")["action"], "reject")


class ParsingAndFlags(unittest.TestCase):
    def test_indented_lines_continue_text_reason_and_quote(self):
        blocks, _ = parse_proposals("\n".join([
            "### SEC-objetivo", "- Tratamiento: seccion", "- Texto: Que la jefatura apruebe",
            "  las altas de monto alto.", '- Cita: "la jefatura aprueba las altas', '  de monto alto"',
            "### RN-06", "- Tratamiento: descarte", "- Motivo: exclusión de alcance", "    ya en GAP-SCOPE",
            "Texto suelto sin sangría", "",
        ]))
        self.assertEqual(blocks["SEC-objetivo"]["text"], "Que la jefatura apruebe las altas de monto alto.")
        self.assertEqual(blocks["SEC-objetivo"]["quote"], "la jefatura aprueba las altas de monto alto")
        self.assertEqual(blocks["RN-06"]["reason"], "exclusión de alcance ya en GAP-SCOPE")

    def test_id_inside_a_longer_id_is_not_a_match(self):
        gap = {"id": "GAP-X-1", "status": "OPEN", "description": "La regla RN-1.2 no cierra con el SAD"}
        self.assertEqual(element_flags("RN-1", "", "", [], [gap], []), [])
        gap["description"] = "La regla RN-1. no cierra con el SAD"
        self.assertEqual(len(element_flags("RN-1", "", "", [], [gap], [])), 1)
        self.assertEqual(len(element_flags("RN-1.2", "", "", [], [{**gap, "description": "ver RN-1.2."}], [])), 1)


if __name__ == "__main__":
    unittest.main()
