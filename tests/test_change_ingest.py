"""IMP-382: /ingest --change opens a CHG with its own scope round, apart from the project."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402

from sentinel.changes import SCOPE_ROUND_IDS, change_gaps_path, get_change, list_changes  # noqa: E402
from sentinel.errors import GateRefusal  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.workspace import read_state, workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class ChangeIngest(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "BORR"])
        cls.out = json.loads(run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"]))

    @property
    def base(self) -> Path:
        return workspace_path("BORR")

    def test_opens_a_change_with_only_the_scope_round(self):
        rows = parse_gap_rows((self.base / "01_discovery" / self.out["change_id"] / "gaps.md").read_text(encoding="utf-8"))
        self.assertTrue(rows)
        self.assertTrue(set(r["id"] for r in rows) <= set(SCOPE_ROUND_IDS))
        self.assertTrue(all(r["parent"].strip("`") == self.out["change_id"] for r in rows))
        self.assertEqual(self.out["round"], "scope")
        self.assertEqual(self.out["change_id"], "CHG-001")

    def test_state_entry_shape(self):
        entry = list_changes("BORR")[self.out["change_id"]]
        self.assertEqual(entry["source"], "00_raw/pedido.md")
        self.assertEqual(entry["round"], "scope")
        self.assertEqual(entry["border"], [])
        self.assertIsNone(entry["border_confirmed_at"])
        self.assertEqual(entry["responses"], [])
        self.assertEqual(get_change("BORR", "CHG-001"), entry)

    def test_change_gaps_path(self):
        self.assertEqual(change_gaps_path(self.base, "CHG-001"), self.base / "01_discovery" / "CHG-001" / "gaps.md")

    def test_project_artifacts_are_untouched(self):
        self.assertFalse((self.base / "01_discovery" / "gaps.md").exists())
        self.assertFalse((self.base / "02_requirements" / "requirements.md").exists())
        self.assertNotIn("raw_input", read_state("BORR").get("artifacts", {}))

    def test_change_and_replace_together_is_an_input_error(self):
        code, _ = run_cli(["ingest", "BORR", "--source", "pedido.md", "--change", "--replace"])
        self.assertNotEqual(code, 0)

    def test_unknown_change_is_refused_with_the_known_ids(self):
        with self.assertRaises(GateRefusal) as caught:
            get_change("BORR", "CHG-009")
        self.assertIn("CHG-009 no es un cambio abierto de BORR", str(caught.exception))
        self.assertIn("CHG-001", caught.exception.next_step)

    def test_second_change_gets_its_own_id(self):
        shutil.copy(FIXTURES / "change_request.md", Path.cwd() / "otro.md")
        out = json.loads(run_ok(["ingest", "BORR", "--source", "otro.md", "--change"]))
        self.assertEqual(out["change_id"], "CHG-002")
        self.assertEqual(sorted(list_changes("BORR")), ["CHG-001", "CHG-002"])


class ChangeLookupWithoutChanges(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        run_ok(["init", "VACIO"])

    def test_refusal_points_to_ingest_change(self):
        with self.assertRaises(GateRefusal) as caught:
            get_change("VACIO", "CHG-001")
        self.assertIn("/ingest VACIO --source NOTA --change", caught.exception.next_step)


if __name__ == "__main__":
    unittest.main()
