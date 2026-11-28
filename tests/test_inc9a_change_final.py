"""IMP-435 (H27 inc 9a) task 4: the working export keeps the sealed final, the consolidation covers every holder,
and a change-only workspace never recommends the backlog of a project it does not have.

Each test repeats the command sequence of the reviewer (docs/evolution/inc9-review): B-06, B-22, B-23.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
import test_change_next  # noqa: E402
import test_h27_consolidated_export  # noqa: E402
from test_h26_cross_record import CID, PID  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

BORR_CID = "CHG-001"


def run_all(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def sha_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DoneChange(SnapshotWorkspaceCase):
    """BORR: a change-only workspace whose change walked to `done` (the sealed final exists)."""

    @classmethod
    def build_workspace(cls):
        test_change_next.ChangeNextSequence.build_workspace()
        test_change_next.ChangeNextSequence("test_each_row_of_the_table_in_order").test_each_row_of_the_table_in_order()

    def exports(self) -> Path:
        return workspace_path("BORR") / "08_context_packs" / "exports"

    def test_plain_export_keeps_final(self):
        """B-06: `/export --artifact brief --change` without `--final` does not rewrite the sealed final."""
        final = self.exports() / f"{BORR_CID}-project-brief.md"
        self.assertTrue(final.is_file())
        before = sha_of(final)
        forget_read_snapshots()
        self.assertEqual(json.loads(run_ok(["next", "BORR", "--change", BORR_CID]))["key"], "done")
        forget_read_snapshots()
        result = json.loads(run_ok(["export", "BORR", "--artifact", "brief", "--change", BORR_CID]))
        draft = self.exports() / f"{BORR_CID}-project-brief-draft.md"
        self.assertTrue(draft.is_file())
        self.assertEqual(Path(result["path"]).name, draft.name)
        self.assertEqual(result["deliverable"], "draft")
        self.assertEqual(sha_of(final), before)
        forget_read_snapshots()
        self.assertEqual(json.loads(run_ok(["next", "BORR", "--change", BORR_CID]))["key"], "done")

    def test_change_only_status_no_project_backlog_warning(self):
        """B-23: the project has no backlog to rebuild, so `/status` does not advise `/backlog BORR`."""
        forget_read_snapshots()
        code, out, err = run_all(["status", "BORR"])
        self.assertEqual(code, 0, err)
        status = json.loads(out)
        text = json.dumps(status, ensure_ascii=False)
        self.assertNotIn("/backlog BORR", text.replace(f"--change {BORR_CID}", ""))
        self.assertNotIn("cannot be verified", text)
        for warning in status["verdict"]["warnings"]:
            self.assertNotIn("backlog", str(warning).lower(), warning)


class EveryHolder(test_h27_consolidated_export.FinalCase):
    def control(self) -> str:
        path = workspace_path(PID) / "01_discovery" / CID / "consolidation_control.md"
        return path.read_text(encoding="utf-8")

    def test_consolidation_flags_every_holder(self):
        """B-22: the decision "the design governs: 1.000.000" also marks PD-01, which still says 5.000.000."""
        self.propose("\n".join([
            "### PD-01", "- Tratamiento: requisito", f"- Líneas: {self.lines_of('PD-01')}",
            '- Cita: "arranca en 5.000.000"',
            "- Enunciado: Cuando el sistema evalúa un alta, debe tomar el umbral de aprobación de un parámetro de configuración.",
            "  - Delta: MODIFIED", "  - Superficie: Aprobación por monto", ""]), "PD-01")
        self.apply()
        row = next(r for r in self.control().splitlines() if r.startswith("| PD-01 "))
        self.assertIn("pendiente", row)
        self.assertIn(self.dis, row)
        run_ok(["brief", PID, "--change", CID])
        forget_read_snapshots()
        # the earlier gates (sections still to extract) say their own thing; the one under test is the consolidation
        with patch("sentinel.deliverables.gate", return_value={"deliverable": "final", "pending_marks": 0}):
            code, _, err = run_all(["export", PID, "--artifact", "brief", "--change", CID, "--final"])
        self.assertEqual(code, 4, err)
        self.assertIn("sin consolidar", err)
        # the BA writes the text of PD-01 with the decision applied and confirms it
        result = self.submit_text("\n".join([
            "### PD-01", f"- Decisión: {self.dis}", f"- Líneas: {self.lines_of('PD-01')}",
            "- Texto: El umbral de aprobación se configura por parámetro y arranca en 1.000.000.", ""]), "pd.md")
        self.assertEqual(result["recorded"], ["PD-01"], result)
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "PD-01"])
        self.assertNotIn("5.000.000", self.final())


class LosingTokens(unittest.TestCase):
    def test_only_significant_numbers_are_losing_tokens(self):
        """M-1: 1-2 digit numbers in a request sentence do not make other elements holders; figures and ids do."""
        from sentinel.extraction.consolidation import _significant_tokens

        sentence = "el umbral de 5.000.000 con 30 días, 2 niveles, 15% de recargo, 500 casos y REQ-ALTA-3 desde $ 40"
        self.assertEqual(_significant_tokens(sentence),
                         ["REQ-ALTA-3", "5.000.000", "15%", "500", "40"])

    def test_bounded_text_short_first_line_keeps_the_body(self):
        """M-7: a short line followed by a very long one is cut at a word, not at the first line."""
        from sentinel.compilers.specs import bounded_text

        text = "Titulo\n" + "palabra " * 100
        cut = bounded_text(text, 200, at_line=True)
        self.assertGreater(len(cut.split("\n\n[TRUNCATED")[0]), 100)


if __name__ == "__main__":
    unittest.main()
