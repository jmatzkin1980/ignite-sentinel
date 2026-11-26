"""H27 inc 7a task 3: a NOT FOUND against a partial baseline asks (once) instead of asserting absence."""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.changes import get_change  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.state import (  # noqa: E402
    baseline_reliability, cross_status, cross_summary, is_partial_baseline, write_cross_report,
)
from sentinel.crosses.surfaces import new_surface_candidates  # noqa: E402
from sentinel.sources import load_source_manifest  # noqa: E402

CID = "CHG-001"
SAD = SyncCase.FIXTURES / "change_baseline" / "sad-compras.md"
PARCIAL = SyncCase.FIXTURES / "change_inc7" / "harvest_parcial.md"
LABEL_ES = "no encontrado en una línea de base parcial: confirmar"
ABSENCE = "No hay una bandeja de aprobaciones"


def run_err(argv: list[str]) -> tuple[int, str]:
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


def rows(pid: str) -> list[dict]:
    forget_read_snapshots()
    return load_source_manifest(pid)["registry"]


def baseline_row(pid: str) -> dict:
    return next(r for r in rows(pid) if r.get("role") == "linea_de_base")


class PartialCase(SyncCase):
    PID = "PARC"

    @classmethod
    def build_workspace(cls) -> None:
        super().build_workspace()
        run_ok(["sources", cls.PID, "--load", str(SAD), "--role", "linea_de_base", "--change", CID,
                "--reliability", "documental"])


class CompleteCase(SyncCase):
    PID = "PARD"


class PartialBaselineTests(PartialCase):
    def test_reliability_declared_and_default(self):
        self.assertEqual(baseline_row(self.PID)["reliability"], "documental")
        self.assertEqual(baseline_reliability(self.PID, CID), "documental")
        self.assertTrue(is_partial_baseline(self.PID, CID))

    def test_partial_not_found_renders_confirm(self):
        forget_read_snapshots()
        text = cross_summary(cross_status(self.PID, CID), "es")
        self.assertIn(f"{LABEL_ES} 2", text)
        self.assertNotIn("NO ENCONTRADO", text)
        english = cross_summary(cross_status(self.PID, CID), "en")
        self.assertIn("not found in a partial baseline: confirm 2", english)
        self.assertNotIn("NOT FOUND", english)
        report = write_cross_report(self.PID, CID).read_text(encoding="utf-8")
        self.assertIn(f"{LABEL_ES} 2", report)
        self.assertNotIn("NO ENCONTRADO", report)
        self.assertIn("## Candidatas a superficie nueva (del harvest, línea de base parcial)", report)
        candidates = new_surface_candidates(self.PID, CID)
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(c["partial"] is True for c in candidates))

    def test_same_absence_asked_once(self):
        shutil.copy(PARCIAL, Path.cwd() / "harvest_parcial.md")
        run_ok(["harvest", self.PID, "--source", "harvest_parcial.md", "--change", CID])
        forget_read_snapshots()
        mine = [c for c in new_surface_candidates(self.PID, CID) if c["text"].startswith(ABSENCE)]
        self.assertEqual(len(mine), 1)
        run_ok(["cross", self.PID, "--change", CID, "--decline-new", mine[0]["id"], "--reason", "ya existe"])
        forget_read_snapshots()
        again = [c for c in new_surface_candidates(self.PID, CID) if c["text"].startswith(ABSENCE)]
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0]["decision"], "declined")
        pending = [c for c in new_surface_candidates(self.PID, CID) if c["decision"] is None]
        self.assertFalse(any(c["text"].startswith(ABSENCE) for c in pending))

    def test_reload_marks_partial(self):
        run_ok(["sources", self.PID, "--load", str(SAD), "--role", "linea_de_base", "--change", CID,
                "--reliability", "codigo"])
        self.assertNotIn("reliability", baseline_row(self.PID))
        self.assertEqual(baseline_reliability(self.PID, CID), "codigo")
        run_ok(["sources", self.PID, "--load", str(SAD), "--role", "linea_de_base", "--change", CID,
                "--reliability", "mixta"])
        self.assertEqual(baseline_row(self.PID)["reliability"], "mixta")
        self.assertTrue(is_partial_baseline(self.PID, CID))

    def test_reliability_refusals(self):
        before = json.dumps(rows(self.PID), sort_keys=True)
        code, err = run_err(["sources", self.PID, "--load", str(SAD), "--role", "diseno_nuevo", "--change", CID,
                             "--reliability", "documental"])
        self.assertNotEqual(code, 0)
        self.assertIn("--reliability va con --role linea_de_base", err)
        code, err = run_err(["sources", self.PID, "--load", str(SAD), "--role", "linea_de_base", "--change", CID,
                             "--reliability", "partial"])
        self.assertNotEqual(code, 0)
        self.assertIn("--reliability es documental, codigo o mixta", err)
        self.assertEqual(json.dumps(rows(self.PID), sort_keys=True), before)


class CompleteBaselineTests(CompleteCase):
    def test_default_is_complete(self):
        self.assertNotIn("reliability", baseline_row(self.PID))
        self.assertEqual(baseline_reliability(self.PID, CID), "codigo")
        self.assertFalse(is_partial_baseline(self.PID, CID))
        text = cross_summary(cross_status(self.PID, CID), "es")
        self.assertIn("NO ENCONTRADO 2", text)
        self.assertNotIn("parcial", text)
        self.assertTrue(all(c["partial"] is False for c in new_surface_candidates(self.PID, CID)))

    def test_first_load_with_flag(self):
        extra = Path.cwd() / "manual-compras.md"
        extra.write_text("# Manual\n\nEl backoffice tiene tres ambientes.\n", encoding="utf-8")
        out = run_ok(["sources", self.PID, "--load", str(extra), "--role", "linea_de_base", "--change", CID,
                      "--reliability", "documental"])
        sid = json.loads(out)["source_id"]
        self.assertEqual(next(r for r in rows(self.PID) if r["id"] == sid)["reliability"], "documental")
        self.assertTrue(is_partial_baseline(self.PID, CID))
        self.assertIn(sid, get_change(self.PID, CID)["sources"])


if __name__ == "__main__":
    unittest.main()
