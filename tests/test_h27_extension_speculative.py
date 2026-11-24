"""IMP-412 (H27 inc 4) task 4: extension proposals and the speculative marks of the request."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, lines_field, run_ok  # noqa: E402
from test_h26_extract_confirm import rn02_one_statement  # noqa: E402
from test_h26_extract_proposals import CID, FIXTURES, PID, ProposalsCase  # noqa: E402

from sentinel.change_requirements import load_change_ears  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.extraction.confirm import confirm_item, confirm_proposals  # noqa: E402
from sentinel.extraction.flags import speculative_marks  # noqa: E402
from sentinel.extraction.inventory import build_inventory  # noqa: E402
from sentinel.extraction.proposals import load_proposals, record_proposals  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

SPECULATIVE = "pedido_especulativo.md"
REASON = "La gerencia lo pidió en la reunión"
RN05_STATEMENT = "Cuando un alta lleva más de 5 días hábiles pendiente, el sistema debe notificar a la gerencia de Compras."
RN02_STATEMENT = (
    "Cuando el analista envía un alta con monto anual estimado mayor al umbral, "
    "el sistema debe dejarla Pendiente de aprobación."
)


def block(element: str, source: str, *lines: str) -> str:
    span = lines_field(element, source)
    return "\n".join([f"### {element}", lines[0], span, *lines[1:], ""])


def rn05_requirement() -> str:
    return block(
        "RN-05", SPECULATIVE, "- Tratamiento: requisito", '- Cita: "se notifica a la gerencia de Compras"',
        f"- Enunciado: {RN05_STATEMENT}", "  - Delta: ADDED", "  - Superficie: Aprobación por monto",
    )


def pd02_discard() -> str:
    return block(
        "PD-02", SPECULATIVE, "- Tratamiento: descarte",
        '- Cita: "La notificación a la gerencia se envía por correo interno"',
        "- Motivo: Es una decisión de canal, no un requisito.",
    )


def typed(text: str, kind: str) -> str:
    return text.rstrip("\n") + f"\n- Tipo: {kind}\n"


class Marks(unittest.TestCase):
    def test_speculative_marks(self):
        self.assertEqual(speculative_marks("PD-02: 🔮 La notificación a la gerencia se envía por correo interno"), ["🔮"])
        self.assertEqual(speculative_marks("se notifica a la gerencia de Compras (a confirmar)."), ["a confirmar"])
        self.assertEqual(speculative_marks("El umbral se confirma por parámetro."), [])
        self.assertEqual(speculative_marks("Tentative y A CONFIRMAR; a confirmar otra vez"), ["a confirmar", "tentative"])


class Extension(ProposalsCase):
    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def item(self) -> dict:
        return load_proposals(workspace_path(PID), CID)["items"]["RN-02"]

    def test_extension_flagged_and_one_by_one(self):
        result = self.submit(typed(rn02_one_statement(), "extension"))
        self.assertEqual(result["flagged"], ["RN-02"])
        self.assertEqual(self.item()["type"], "extension")
        self.assertIn("extension", [f["kind"] for f in self.item()["flags"]])
        self.assertEqual(confirm_proposals(PID, CID, "all")["held"], ["RN-02"])
        self.assertEqual(confirm_item(PID, CID, "RN-02")["confirmed"], ["RN-02"])
        self.assertEqual(self.item()["status"], "confirmed")
        self.assertIn("extension", [f["kind"] for f in self.item()["flags"]])  # the trace stays

    def test_extension_confirms_delegated_too(self):
        self.submit(typed(rn02_one_statement(), "extension"))
        result = confirm_item(PID, CID, "RN-02", delegated=True, note="Ana, por la jefa")
        self.assertEqual(result["delegated"], ["RN-02"])
        self.assertEqual(self.item()["confirmed_by"], "delegated")

    def test_default_type_and_bad_type(self):
        self.submit(rn02_one_statement())
        self.assertEqual(self.item()["type"], "aplica")
        self.assertNotIn("extension", [f["kind"] for f in self.item()["flags"]])
        result = self.submit(typed(rn02_one_statement(), "otro"), "q.md")
        self.assertEqual(result["rejected"]["RN-02"], ["RN-02: Tipo debe ser aplica o extension"])


class Speculative(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / SPECULATIVE, root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        (root / "spec.md").write_text(rn05_requirement() + "\n" + pd02_discard(), encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        build_inventory(PID, CID)

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.result = record_proposals(PID, CID, Path.cwd() / "spec.md")

    def items(self) -> dict:
        return load_proposals(workspace_path(PID), CID)["items"]

    def test_speculative_requirement_needs_reason(self):
        self.assertEqual(self.result["recorded"], ["RN-05", "PD-02"])
        marks = [f for f in self.items()["RN-05"]["flags"] if f["kind"] == "a_confirmar"]
        self.assertEqual([(m["origin"], m["note"]) for m in marks], [("request", "a confirmar")])
        self.assertIn("RN-05", confirm_proposals(PID, CID, "all")["held"])
        with self.assertRaises(InputError) as caught:
            confirm_item(PID, CID, "RN-05")
        self.assertIn("el pedido lo marca como a confirmar («a confirmar»)", str(caught.exception))
        self.assertEqual(self.items()["RN-05"]["status"], "proposed")
        self.assertEqual(confirm_item(PID, CID, "RN-05", reason=REASON)["confirmed"], ["RN-05"])
        item = self.items()["RN-05"]
        self.assertIs(item["a_confirmar"], True)
        self.assertEqual(item["a_confirmar_reason"], REASON)
        self.assertIn("a_confirmar", [f["kind"] for f in item["flags"]])  # the trace stays
        rows = load_change_ears(PID, CID)
        self.assertEqual(len(rows), 1)
        self.assertIs(rows[0]["a_confirmar"], True)
        self.assertTrue(rows[0]["source"].endswith(" / `a_confirmar`"))
        self.assertTrue(rows[0]["source"].startswith("`EXT:RN-05`"))

    def test_other_elements_rows_have_no_key(self):
        extra = block(
            "RN-02", SPECULATIVE, "- Tratamiento: requisito", '- Cita: "requiere aprobación de la jefa de Compras"',
            f"- Enunciado: {RN02_STATEMENT}", "  - Delta: ADDED", "  - Superficie: Aprobación por monto",
        )
        (Path.cwd() / "extra.md").write_text(extra, encoding="utf-8")
        record_proposals(PID, CID, Path.cwd() / "extra.md")
        confirm_item(PID, CID, "RN-05", reason=REASON)
        confirm_item(PID, CID, "RN-02")
        rows = load_change_ears(PID, CID)
        self.assertEqual(sorted("a_confirmar" in row for row in rows), [False, True])
        self.assertNotIn("a_confirmar", self.items()["RN-02"])

    def test_speculative_discard_needs_reason(self):
        self.assertEqual([f["note"] for f in self.items()["PD-02"]["flags"] if f["kind"] == "a_confirmar"], ["🔮"])
        self.assertIn("PD-02", confirm_proposals(PID, CID, "all")["held"])
        with self.assertRaises(InputError) as caught:
            confirm_item(PID, CID, "PD-02")
        self.assertIn("el pedido lo marca como a confirmar («🔮»)", str(caught.exception))
        self.assertEqual(confirm_item(PID, CID, "PD-02", reason=REASON)["confirmed"], ["PD-02"])
        self.assertIs(self.items()["PD-02"]["a_confirmar"], True)

    def test_delegated_path_also_needs_reason(self):
        with self.assertRaises(InputError):
            confirm_item(PID, CID, "RN-05", delegated=True, note="Ana, por la jefa")
        result = confirm_item(PID, CID, "RN-05", delegated=True, note="Ana, por la jefa", reason=REASON)
        self.assertEqual(result["delegated"], ["RN-05"])
        item = self.items()["RN-05"]
        self.assertEqual((item["confirmed_by"], item["a_confirmar_reason"]), ("delegated", REASON))

    def test_cli_reason_goes_with_confirm_item(self):
        out = run_ok(["extract", PID, "--change", CID, "--confirm-item", "RN-05", "--reason", REASON])
        self.assertEqual(json.loads(out)["confirmed"], ["RN-05"])

    def test_brief_shows_a_confirmar(self):
        confirm_item(PID, CID, "RN-05", reason=REASON)
        run_ok(["brief", PID, "--change", CID])
        internal = (workspace_path(PID) / "02_requirements" / CID / "project-brief.md").read_text(encoding="utf-8")
        self.assertIn(f"— a confirmar: {REASON}", internal)
        forget_read_snapshots()
        exported = json.loads(run_ok(["export", PID, "--artifact", "brief", "--change", CID]))
        self.assertIn(f"— a confirmar: {REASON}", Path(exported["path"]).read_text(encoding="utf-8"))
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertEqual(status["a_confirmar"], ["RN-05"])

    def test_status_has_no_key_without_a_confirmar(self):
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertNotIn("a_confirmar", status)


if __name__ == "__main__":
    unittest.main()
