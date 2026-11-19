"""IMP-382: /gaps --change regenerates a change's gaps; refusals point to the change."""
from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402

from sentinel.changes import border_types, change_gaps_path, list_changes, regenerate_change_gaps  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.workspace import read_state, update_state, workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run_err(argv: list[str]) -> tuple[int, str]:
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


class ChangeGaps(SnapshotWorkspaceCase):
    change_id = "CHG-001"

    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])

    @property
    def base(self) -> Path:
        return workspace_path("BORR")

    def change_gaps_text(self) -> str:
        return change_gaps_path(self.base, self.change_id).read_text(encoding="utf-8")

    def test_unknown_change_is_refused_with_known_ids(self):
        code, err = run_err(["gaps", "BORR", "--change", "CHG-999"])
        self.assertNotEqual(code, 0)
        self.assertIn("CHG-999 no es un cambio abierto de BORR", err)
        self.assertIn(self.change_id, err)

    def test_plain_gaps_on_change_only_workspace_points_to_change(self):
        code, err = run_err(["gaps", "BORR"])
        self.assertNotEqual(code, 0)
        self.assertIn("sólo tiene cambios", err)
        self.assertIn(f"--change {self.change_id}", err)

    def test_scope_round_regenerates_without_new_rows(self):
        before = self.change_gaps_text()
        out = json.loads(run_ok(["gaps", "BORR", "--change", self.change_id]))
        self.assertEqual(parse_gap_rows(before), parse_gap_rows(self.change_gaps_text()))
        self.assertEqual(out["round"], "scope")
        self.assertEqual(out["change_id"], self.change_id)
        self.assertEqual(read_state("BORR")["changes"][self.change_id]["gap_counts"], out["gap_counts"])
        self.assertFalse(read_state("BORR").get("gap_counts"))

    def test_border_types(self):
        self.assertEqual(border_types({"border": []}), frozenset())
        self.assertEqual(
            border_types({"border": [{"type": "pantalla"}, {"type": "dato"}, {"type": "pantalla"}]}),
            frozenset({"pantalla", "dato"}),
        )

    def test_lens_round_adds_checks_once_and_keeps_scope_rows(self):
        scope_ids = [r["id"] for r in parse_gap_rows(self.change_gaps_text())]
        changes = {k: dict(v) for k, v in list_changes("BORR").items()}
        changes[self.change_id]["round"] = "lenses"
        changes[self.change_id]["border"] = [{"type": "pantalla", "name": "Borrador"}]
        update_state("BORR", changes=changes)
        first = regenerate_change_gaps("BORR", self.change_id)
        ids = [r["id"] for r in parse_gap_rows(self.change_gaps_text())]
        self.assertEqual(ids[: len(scope_ids)], scope_ids)
        self.assertGreater(len(ids), len(scope_ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(first["round"], "lenses")
        again = regenerate_change_gaps("BORR", self.change_id)
        self.assertEqual([r["id"] for r in parse_gap_rows(self.change_gaps_text())], ids)
        self.assertEqual(again["gap_counts"], first["gap_counts"])

    def test_project_path_is_untouched(self):
        run_ok(["gaps", "BORR", "--change", self.change_id])
        self.assertFalse((self.base / "01_discovery" / "gaps.md").exists())
        self.assertFalse((self.base / "01_discovery" / "gap_elicitation.json").exists())


if __name__ == "__main__":
    unittest.main()
