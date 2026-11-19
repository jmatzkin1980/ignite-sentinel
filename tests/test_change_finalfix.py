"""IMP-382 final review fixes: raw collisions, GAP-SCOPE always in scope, language, CLI flag conflicts."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402
from test_change_gaps import run_err  # noqa: E402

from sentinel.changes import change_gaps_path, get_change, list_changes  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.lens_registry import load_lens_checks  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BORDER = [
    'nuevo | pantalla | Botón "Guardar borrador" en el alta de proveedores',
    "adyacente | endpoint | Envío actual del alta de proveedores",
    "preservado | proceso | Envío completo del alta",
]


def answer(status: str = "confirmado", border: bool = True) -> str:
    lines = ["### GAP-SCOPE", "- Respuesta: Sólo el formulario de alta de proveedores."]
    if border:
        lines.append("- Borde:")
        lines += [f"  - {line}" for line in BORDER]
    lines += ["- Owner / fuente: Jefa de Compras", f"- Estado de decisión: {status}", ""]
    return "\n".join(lines)


class RawCollision(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        (root / "pedido.md").write_text("# Proyecto\nEl proyecto original de compras.\n", encoding="utf-8")
        (root / "otro").mkdir()
        shutil.copy(FIXTURES / "change_borrador.md", root / "otro" / "pedido.md")
        run_ok(["init", "COL"])
        run_ok(["ingest", "COL", "--source", "pedido.md"])

    def test_change_does_not_overwrite_the_project_raw_copy(self):
        raw = workspace_path("COL") / "00_raw" / "pedido.md"
        before = raw.read_bytes()
        out = json.loads(run_ok(["ingest", "COL", "--source", "otro/pedido.md", "--change"]))
        self.assertEqual(raw.read_bytes(), before)
        stored = get_change("COL", out["change_id"])["source"]
        self.assertNotEqual(stored, "00_raw/pedido.md")
        self.assertTrue((workspace_path("COL") / stored).exists())
        self.assertIn("Guardar borrador", (workspace_path("COL") / stored).read_text(encoding="utf-8"))

    def test_reingesting_the_same_change_file_is_still_refused(self):
        run_ok(["ingest", "COL", "--source", "otro/pedido.md", "--change"])
        entry = json.dumps(list_changes("COL"), sort_keys=True)
        code, _ = run_cli(["ingest", "COL", "--source", "otro/pedido.md", "--change"])
        self.assertNotEqual(code, 0)
        self.assertEqual(json.dumps(list_changes("COL"), sort_keys=True), entry)


class ScopeAlwaysAsked(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        text = (FIXTURES / "change_borrador.md").read_text(encoding="utf-8")
        (root / "pedido.md").write_text(text + "\nAlcance: sólo el formulario de alta.\n", encoding="utf-8")
        (root / "scope.md").write_text(answer(), encoding="utf-8")
        (root / "pending.md").write_text(answer("pendiente", border=False), encoding="utf-8")
        (root / "second.md").write_text("### GAP-OBJECTIVE\n- Respuesta: Evitar perder cargas.\n- Estado de decisión: pendiente\n", encoding="utf-8")
        run_ok(["init", "SCO"])
        run_ok(["ingest", "SCO", "--source", "pedido.md", "--change"])

    def test_gap_scope_is_in_the_scope_round_even_with_the_word_alcance(self):
        rows = parse_gap_rows(change_gaps_path(workspace_path("SCO"), "CHG-001").read_text(encoding="utf-8"))
        self.assertIn("GAP-SCOPE", {row["id"] for row in rows})
        scope_check = next(c for c in load_lens_checks() if c["id"] == "GAP-SCOPE")
        row = next(r for r in rows if r["id"] == "GAP-SCOPE")
        self.assertEqual(row["severity"], scope_check["severity"])

    def test_confirmed_border_reaches_the_lens_round(self):
        run_ok(["resolve-gaps", "SCO", "--source", "scope.md", "--change", "CHG-001"])
        self.assertEqual(get_change("SCO", "CHG-001")["round"], "lenses")

    def test_pending_answer_keeps_spanish_and_second_answer_appends(self):
        run_ok(["resolve-gaps", "SCO", "--source", "pending.md", "--change", "CHG-001"])
        gaps = change_gaps_path(workspace_path("SCO"), "CHG-001")
        self.assertIn("# Gaps de Discovery", gaps.read_text(encoding="utf-8"))
        self.assertEqual(get_change("SCO", "CHG-001")["language"], "es")
        run_ok(["resolve-gaps", "SCO", "--source", "second.md", "--change", "CHG-001"])
        self.assertEqual(len(get_change("SCO", "CHG-001")["responses"]), 2)
        self.assertIn("# Gaps de Discovery", gaps.read_text(encoding="utf-8"))

    def test_lens_rows_persist_after_a_later_answer(self):
        run_ok(["resolve-gaps", "SCO", "--source", "scope.md", "--change", "CHG-001"])
        gaps = change_gaps_path(workspace_path("SCO"), "CHG-001")
        ids = {r["id"] for r in parse_gap_rows(gaps.read_text(encoding="utf-8"))}
        self.assertGreater(len(ids), 4)
        run_ok(["resolve-gaps", "SCO", "--source", "second.md", "--change", "CHG-001"])
        after = {r["id"] for r in parse_gap_rows(gaps.read_text(encoding="utf-8"))}
        self.assertEqual(ids, after)
        self.assertEqual(len(get_change("SCO", "CHG-001")["responses"]), 2)


class GapsChangeFlagConflicts(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "FLG"])
        run_ok(["ingest", "FLG", "--source", "pedido.md", "--change"])

    def test_change_with_id_or_top_is_refused(self):
        for extra in (["--id", "GAP-SCOPE", "--disposition", "accepted"], ["--top", "3"]):
            code, err = run_err(["gaps", "FLG", "--change", "CHG-001", *extra])
            self.assertNotEqual(code, 0, extra)
            self.assertIn("--change", err)


class EmptyAppliesTo(unittest.TestCase):
    def test_empty_applies_to_is_rejected(self):
        from sentinel.lens_registry import _validate_check_scope

        with self.assertRaises(ValueError):
            _validate_check_scope({"id": "GAP-X", "applies_to": []})
        _validate_check_scope({"id": "GAP-X", "applies_to": ["change"]})


if __name__ == "__main__":
    unittest.main()
