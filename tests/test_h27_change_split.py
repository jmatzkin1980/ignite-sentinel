"""IMP-427 (H27 inc 7c) tasks 2 and 3: `/split P --change CHG` assesses, proposes and confirms the series of a change.

The files live under the change, no project brief is needed and nothing of the project or of another change moves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.series_scope import series_scope  # noqa: E402
from sentinel.split_proposal import SplitProposalError, apply_proposal  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "CSPL"
CID = "CHG-001"
INC7 = Path(__file__).resolve().parent / "fixtures" / "change_inc7"


class ChangeSplitCase(SyncCase):
    PID = PID

    def base(self) -> Path:
        return workspace_path(PID)

    def propose(self, name: str = "propuesta_serie_cambio.json") -> str:
        return run_ok(["split", PID, "--propose", "--source", str(INC7 / name), "--change", CID])


class ChangeProposeTest(ChangeSplitCase):
    def test_change_assess_writes_under_change(self) -> None:
        run_ok(["split", PID, "--assess", "--change", CID])
        base = self.base()
        self.assertTrue((base / "01_discovery" / CID / "split_assessment.md").is_file())
        self.assertFalse((base / "01_discovery" / "split_assessment.md").exists())
        data = json.loads((base / "01_discovery" / CID / "split_assessment.json").read_text(encoding="utf-8"))
        self.assertEqual(data["brief_sha256"], series_scope(PID, CID).brief_sha256)

    def test_change_proposal_needs_no_project_brief(self) -> None:
        base = self.base()
        self.assertFalse((base / "02_requirements" / "project-brief.md").exists())
        self.assertFalse((base / "02_requirements" / "brief_compile_report.json").exists())
        out = json.loads(self.propose())
        self.assertEqual(out["status"], "proposal")
        stored = json.loads((base / "02_requirements" / CID / "series" / "proposal.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["brief_sha256"], series_scope(PID, CID).brief_sha256)

    def test_change_never_reads_project_report_or_settings(self) -> None:
        with patch("sentinel.split.read_state", side_effect=AssertionError("project state read")), \
                patch("sentinel.split.read_json", side_effect=AssertionError("project report read")):
            from sentinel.split import _inputs
            scope, report, settings, _gaps = _inputs(PID, CID)
        self.assertIsInstance(report, dict)
        self.assertEqual(settings, {})
        self.assertEqual(scope.change_id, CID)

    def test_invented_citation_refused(self) -> None:
        with self.assertRaises(SplitProposalError) as caught:
            apply_proposal(PID, INC7 / "propuesta_cita_inventada.json", CID)
        self.assertIn("Pagos a proveedores en el exterior", str(caught.exception))
        self.assertFalse((self.base() / "02_requirements" / CID / "series" / "proposal.json").exists())

    def test_change_series_isolated(self) -> None:
        run_ok(["ingest", PID, "--source", str(self.FIXTURES / "change_request.md"), "--change"])
        self.propose()
        base = self.base()
        self.assertFalse((base / "02_requirements" / "series").exists())
        self.assertFalse((base / "02_requirements" / "CHG-002" / "series").exists())

    def test_mcp_split_passes_change(self) -> None:
        import sentinel.mcp as mcp
        from test_mcp_parity import _tools

        tools = _tools()
        calls: list[list[str]] = []
        with patch.object(mcp, "run_cli", side_effect=lambda argv: calls.append(list(argv)) or {}):
            tools["sentinel_split"](PID, mode="assess", change=CID)
        self.assertEqual(calls[0], ["split", PID, "--assess", "--change", CID])


class ChangeConfirmTest(ChangeSplitCase):
    def confirm(self) -> str:
        self.propose()
        return run_ok(["split", PID, "--confirm", "--ba", "Ana", "--tech", "Equipo", "--change", CID])

    def test_change_confirm_compiles_series(self) -> None:
        self.confirm()
        req = self.base() / "02_requirements"
        for name in ("partition.json", "index.md", "release-guide.md"):
            self.assertTrue((req / CID / "series" / name).is_file(), name)
        for rid in ("r1", "r2"):
            self.assertTrue((req / CID / rid / "project-brief.md").is_file(), rid)
        self.assertFalse((req / "r1").exists())
        self.assertFalse((req / "series").exists())
        index = (req / CID / "series" / "index.md").read_text(encoding="utf-8")
        self.assertIn("Compilada desde el entregable de CHG-001", index)
        self.assertIn(f"02_requirements/{CID}/series/index.md", (req / CID / "r1" / "project-brief.md").read_text(encoding="utf-8"))

    def test_change_guide_language_and_content(self) -> None:
        from sentinel.release_series import _plain

        self.confirm()
        guide = (self.base() / "02_requirements" / CID / "series" / "release-guide.md").read_text(encoding="utf-8")
        self.assertTrue(guide.startswith("# Guía de la serie — CSPL · CHG-001"))
        self.assertIn("r1 Alta de proveedor", guide)
        self.assertIn("r2 Aprobación de jefatura", guide)
        self.assertIn("abierto; las sub-releases de un cambio todavía no se derivan", guide)
        self.assertNotIn("/specs --release", guide)
        lines = {_plain(line)[:90] for line in series_scope(PID, CID).brief_text.splitlines()}
        matrix = guide.split("| Familia | Unidad | Dueño |")[1].split("##")[0]
        units = [row.split("|")[2].strip() for row in matrix.splitlines() if row.startswith("| ") and "---" not in row]
        self.assertTrue(units)
        for unit in units:
            self.assertIn(unit, lines)

    def test_client_gap_in_change_gaps(self) -> None:
        from sentinel.changes import change_gaps_path

        self.confirm()
        text = change_gaps_path(self.base(), CID).read_text(encoding="utf-8")
        self.assertIn("GAP-SPLIT-CLIENT", text)
        self.assertFalse((self.base() / "01_discovery" / "gaps.md").exists())

    def _maps(self) -> tuple[dict, dict]:
        series = self.base() / "02_requirements" / CID / "series"
        return (json.loads((series / "series_map.json").read_text(encoding="utf-8")),
                json.loads((series / "partition.json").read_text(encoding="utf-8")))

    def test_confirm_pins_the_brief_despite_the_client_gap(self) -> None:
        """I1: the series' own gap is not a change of the brief."""
        self.confirm()
        series_map, partition = self._maps()
        self.assertEqual(series_map["brief_sha256"], partition["brief_sha256"])
        self.assertEqual(series_scope(PID, CID).brief_sha256, partition["brief_sha256"])
        index = (self.base() / "02_requirements" / CID / "series" / "index.md").read_text(encoding="utf-8")
        self.assertNotIn("El brief cambió desde la confirmación", index)

    def test_confirm_twice_with_same_proposal(self) -> None:
        self.confirm()
        out = run_ok(["split", PID, "--confirm", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        self.assertIn("confirmed", out)

    def test_next_utc_day_is_not_stale(self) -> None:
        """I2: the seal date is not content of the change."""
        self.propose()
        with patch("sentinel.compilers.change_deliverable.utc_now", return_value="2099-01-01T00:00:00Z"):
            self.assertEqual(series_scope(PID, CID).brief_sha256, self._stored_sha())
            run_ok(["split", PID, "--confirm", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
            series_map, partition = self._maps()
            self.assertEqual(series_map["brief_sha256"], partition["brief_sha256"])

    def _stored_sha(self) -> str:
        stored = json.loads((self.base() / "02_requirements" / CID / "series" / "proposal.json").read_text(encoding="utf-8"))
        return stored["brief_sha256"]

    def test_content_change_makes_series_stale(self) -> None:
        from sentinel.core.io import forget_read_snapshots

        self.confirm()
        answer = Path.cwd() / "otra.md"
        answer.write_text("### GAP-QUALITY\n- Respuesta: El alta responde en menos de dos segundos con 500 altas por hora.\n"
                          "- Owner / fuente: Jefa de Compras\n- Estado de decisión: confirmado\n", encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", str(answer), "--change", CID])
        forget_read_snapshots()
        series_map, _ = self._maps()
        self.assertNotEqual(series_scope(PID, CID).brief_sha256, series_map["brief_sha256"])

    def test_reconfirm_reopens_closed_client_gap(self) -> None:
        from sentinel.changes import change_gaps_path
        from sentinel.core.io import forget_read_snapshots, write_text
        from sentinel.gaps import parse_gap_rows, render_gaps

        self.confirm()
        path = change_gaps_path(self.base(), CID)
        rows = [r for r in parse_gap_rows(path.read_text(encoding="utf-8")) if r.get("id") != "NONE"]
        for row in rows:
            if row["id"].strip("`") == "GAP-SPLIT-CLIENT":
                row.update(status="CLOSED", resolution_note="Cliente conforme")
        write_text(path, render_gaps(PID, rows, CID, "es", path.with_name("gap_elicitation.json")))
        forget_read_snapshots()
        run_ok(["split", PID, "--confirm", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        after = {r["id"].strip("`"): r for r in parse_gap_rows(path.read_text(encoding="utf-8"))}
        self.assertEqual(after["GAP-SPLIT-CLIENT"]["status"].upper(), "OPEN")

    def test_normalized_text_drops_the_seal_block(self) -> None:
        from sentinel.series_scope import normalized_change_text

        text = ("> **Estado:** borrador · **Fecha:** 2026-01-01 · **Veredicto:** x\n> **Status:** draft · **Date:** 2026-01-01\n"
                "| `GAP-A`: q | a |\nbody")
        self.assertEqual(normalized_change_text(text), "| `GAP-A`: q | a |\nbody")

    def test_refresh_reads_no_brief_without_assessment_or_series(self) -> None:
        """M2: nothing stored, nothing to refresh, and no brief is read or hashed."""
        from sentinel.release_series import refresh_series_if_stale
        from sentinel.split import refresh_if_stale

        with patch("sentinel.series_scope._project_scope", side_effect=AssertionError("brief read")):
            self.assertIsNone(refresh_if_stale(PID))
            self.assertIsNone(refresh_series_if_stale(PID))

    def test_reconsolidated_change_refuses_confirm(self) -> None:
        from sentinel.core.io import forget_read_snapshots
        from sentinel.errors import InputError

        self.propose()
        answer = Path.cwd() / "otra.md"
        answer.write_text("### GAP-QUALITY\n- Respuesta: El alta responde en menos de dos segundos con 500 altas por hora.\n"
                          "- Owner / fuente: Jefa de Compras\n- Estado de decisión: confirmado\n", encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", str(answer), "--change", CID])
        forget_read_snapshots()
        from sentinel.release_split import confirm_partition

        with self.assertRaises(InputError) as caught:
            confirm_partition(PID, "Ana", "Equipo", CID)
        self.assertIn("the brief changed since the proposal was stored; run /split --propose again", str(caught.exception))


class ChangeRefusalsTest(ChangeSplitCase):
    """Task 4 (RF 4): what needs the sub-releases of a change (7d) is refused, and the guide shows with --change."""

    @staticmethod
    def cli(argv: list[str]) -> tuple[int, str]:
        import io
        from contextlib import redirect_stderr, redirect_stdout

        from sentinel.cli import main

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def partition_sha(self) -> str:
        import hashlib

        return hashlib.sha256((self.base() / "02_requirements" / CID / "series" / "partition.json").read_bytes()).hexdigest()

    def test_close_move_release_refuse_with_change(self) -> None:
        self.propose()
        run_ok(["split", PID, "--confirm", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        before = self.partition_sha()
        message = ("/split --close y --move con --change llegan con las sub-releases de un cambio; "
                   "hoy: --assess, --propose o --confirm")
        for argv in (["split", PID, "--close", "r1", "--change", CID, "--evidence", "x", "--ba", "Ana", "--tech", "Equipo"],
                     ["split", PID, "--move", "--unit", "U", "--from", "r1", "--to", "r2", "--reason", "x", "--ba", "Ana",
                      "--tech", "Equipo", "--change", CID]):
            code, out = self.cli(argv)
            self.assertNotEqual(code, 0)
            self.assertIn(message, out)
        self.assertEqual(self.partition_sha(), before)
        code, out = self.cli(["next", PID, "--change", CID, "--release", "r1"])
        self.assertNotEqual(code, 0)
        self.assertIn("--release con --change existe para /specs y /backlog", out)

    def test_view_change_release_guide(self) -> None:
        self.propose()
        run_ok(["split", PID, "--confirm", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        run_ok(["view", PID, "--artifact", "release-guide", "--change", CID])
        self.assertTrue((self.base() / "08_context_packs" / "views" / f"{CID}-release-guide.html").is_file())
        code, out = self.cli(["view", PID, "--artifact", "prd", "--change", CID])
        self.assertNotEqual(code, 0)
        self.assertIn("sólo admite", out)
