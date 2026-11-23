"""IMP-404 (H26 inc 4) task 3: record a cross-read, waive it, open its questions, its status and summary."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402

from sentinel.changes import change_gaps_path, list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots, read_json  # noqa: E402
from sentinel.crosses import cross_path, crosses_dir  # noqa: E402
from sentinel.crosses.record import CrossError, GAP_PREFIXES, cross_gap, load_cross, record_cross, skip_cross  # noqa: E402
from sentinel.crosses.state import cross_status, crosses_fingerprint  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.sources import load_source_manifest  # noqa: E402
from sentinel.status import change_sources  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CROSSES = FIXTURES / "change_crosses"
PID = "CRZR"
CID = "CHG-001"


def set_language(project: str, language: str) -> None:
    changes = {key: dict(value) for key, value in list_changes(project).items()}
    changes[CID]["language"] = language
    update_state(project, changes=changes)


class CrossCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(CROSSES / "pedido_contradiccion.md", root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(CROSSES / "prototipo-aprobaciones.html"),
                "--role", "diseno_nuevo", "--change", CID])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def ids(self) -> dict[str, str]:
        found = change_sources(PID, CID)
        return {"pedido": found["by_role"]["pedido"][0], "diseno": found["by_role"]["diseno_nuevo"][0]}

    def write(self, name: str, drop_solo: bool = False) -> Path:
        ids = self.ids()
        text = (CROSSES / name).read_text(encoding="utf-8").replace("F-PED", ids["pedido"]).replace("F-DIS", ids["diseno"])
        if drop_solo:
            lines = text.splitlines()
            start = next(i for i, line in enumerate(lines) if line.startswith("- [SOLO EN DISEÑO]"))
            text = "\n".join(lines[:start] + lines[start + 2:]) + "\n"
        path = Path.cwd() / f"sub-{len(list(Path.cwd().glob('sub-*')))}-{name}"
        path.write_text(text, encoding="utf-8")
        return path

    def gaps(self) -> dict[str, dict]:
        path = change_gaps_path(workspace_path(PID), CID)
        return {g["id"]: g for g in parse_gap_rows(path.read_text(encoding="utf-8"))}


class Recording(CrossCase):
    def test_record_design_cross(self):
        before = list_changes(PID)[CID]["gap_counts"]["blocking_open"]
        file = self.write("cruce_diseno.md")
        result = record_cross(PID, CID, "diseno", file)
        self.assertEqual(result["action"], "claims")
        self.assertEqual(result["counts"], {"respaldado": 2, "sin_respaldo": 1, "solo_en_diseno": 1, "divergencia": 1})
        self.assertEqual(sorted(g[:8] for g in result["gaps_opened"]), ["GAP-DIS-", "GAP-SED-", "GAP-SRD-"])
        gaps = self.gaps()
        dis = next(g for i, g in gaps.items() if i.startswith("GAP-DIS-"))
        srd = next(g for i, g in gaps.items() if i.startswith("GAP-SRD-"))
        self.assertEqual(dis["severity"], "high")
        self.assertIn("(A) rige el diseño", dis["question"])
        self.assertEqual(srd["severity"], "medium")
        text = change_gaps_path(workspace_path(PID), CID).read_text(encoding="utf-8")
        section = text.split(f"### {dis['id']}")[1].split("### ")[0]
        self.assertNotIn("Opciones candidatas citadas", section)
        self.assertEqual(list_changes(PID)[CID]["gap_counts"]["blocking_open"], before + 1)
        base = workspace_path(PID)
        record = read_json(cross_path(base, CID, "diseno"), {})
        self.assertEqual(record["status"], "done")
        self.assertEqual(record["gaps"], result["gaps"])
        self.assertTrue((crosses_dir(base, CID) / "submitted" / f"001-{file.name}").is_file())
        self.assertTrue((crosses_dir(base, CID) / "crosses.md").is_file())
        rows = load_source_manifest(PID)["registry"]
        crossed = [r for r in rows if any(e.get("via") == "crossed" for e in r.get("events") or [])]
        self.assertEqual(len(crossed), 1)

    def test_record_contradiction_is_blocking(self):
        result = record_cross(PID, CID, "contradicciones", self.write("cruce_contradicciones.md"))
        (gap_id,) = result["gaps_opened"]
        self.assertTrue(gap_id.startswith("GAP-CON-"))
        gap = self.gaps()[gap_id]
        self.assertEqual(gap["severity"], "high")
        self.assertEqual(len(gap["evidence_mention"].split(" // ")), 2)

    def test_rejected_file_writes_nothing(self):
        path = self.write("cruce_diseno.md")
        path.write_text(path.read_text(encoding="utf-8").replace("Delegar aprobaciones", "Pantalla inexistente total"),
                        encoding="utf-8")
        gaps_before = change_gaps_path(workspace_path(PID), CID).read_text(encoding="utf-8")
        rows_before = len(load_source_manifest(PID)["registry"])
        with self.assertRaises(CrossError) as ctx:
            record_cross(PID, CID, "diseno", path)
        self.assertIn("Cruce rechazado", str(ctx.exception))
        self.assertFalse(cross_path(workspace_path(PID), CID, "diseno").exists())
        self.assertEqual(change_gaps_path(workspace_path(PID), CID).read_text(encoding="utf-8"), gaps_before)
        self.assertEqual(len(load_source_manifest(PID)["registry"]), rows_before)

    def test_baseline_kind_is_the_harvest(self):
        with self.assertRaises(CrossError) as ctx:
            record_cross(PID, CID, "linea_de_base", self.write("cruce_diseno.md"))
        self.assertIn("es el harvest", str(ctx.exception))
        self.assertIn("/harvest", ctx.exception.next_step)

    def test_resubmission_keeps_gap_ids(self):
        first = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        second = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        self.assertEqual(second["gaps"], first["gaps"])
        self.assertEqual(second["gaps_opened"], [])
        self.assertEqual(second["dropped_gaps"], [])
        third = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md", drop_solo=True))
        (sed,) = [g for g in first["gaps"] if g.startswith("GAP-SED-")]
        self.assertEqual(third["dropped_gaps"], [sed])
        self.assertEqual(self.gaps()[sed]["status"], "OPEN")
        base = workspace_path(PID)
        report = (crosses_dir(base, CID) / "crosses.md").read_text(encoding="utf-8")
        self.assertIn(sed, report)
        self.assertIn("siguen abiertas", report)
        self.assertEqual(len(list((crosses_dir(base, CID) / "submitted").glob("00*"))), 3)

    def test_gap_id_is_stable_and_by_content(self):
        claim = {"tag": "sin_respaldo", "text": "x", "citations": [
            {"side": "pedido", "source_id": "F-01", "quote": "una   cita\nlarga del pedido", "line": 3}]}
        gap = cross_gap(CID, claim, "es")
        self.assertEqual(gap["id"], cross_gap(CID, {**claim, "text": "otro texto"}, "es")["id"])
        self.assertTrue(gap["id"].startswith("GAP-SRD-") and len(gap["id"]) == len("GAP-SRD-") + 8)
        self.assertIsNone(cross_gap(CID, {**claim, "tag": "respaldado"}, "es"))
        self.assertEqual(set(GAP_PREFIXES), {"divergencia", "sin_respaldo", "solo_en_diseno", "contradiccion"})


class Skipping(CrossCase):
    def test_skip_needs_reason_and_refuses_done(self):
        with self.assertRaises(InputError):
            skip_cross(PID, CID, "contradicciones", "")
        result = skip_cross(PID, CID, "contradicciones", "El pedido es corto")
        self.assertEqual(result["action"], "skip")
        record = read_json(cross_path(workspace_path(PID), CID, "contradicciones"), {})
        self.assertEqual(record["status"], "waived")
        self.assertEqual(record["reason"], "El pedido es corto")
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        with self.assertRaises(InputError) as ctx:
            skip_cross(PID, CID, "diseno", "x")
        self.assertIn("ya está hecho", str(ctx.exception))
        self.assertEqual(load_cross(workspace_path(PID), CID, "diseno")["status"], "done")

    def test_claims_file_is_not_a_source_with_role(self):
        file = self.write("cruce_diseno.md")
        record_cross(PID, CID, "diseno", file)
        code, _ = run_cli(["sources", PID, "--load", str(file), "--role", "diseno_nuevo", "--change", CID])
        self.assertNotEqual(code, 0)
        from sentinel.sources import load_source

        with self.assertRaises(InputError) as ctx:
            load_source(PID, file, "diseno_nuevo", CID)
        self.assertIn("lectura de Sentinel", str(ctx.exception))


class Status(CrossCase):
    def test_status_and_summary(self):
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        skip_cross(PID, CID, "contradicciones", "El pedido es corto")
        status = cross_status(PID, CID)
        self.assertEqual(status["missing"], ["linea_de_base"])
        self.assertFalse(status["complete"])
        self.assertIn("diseño nuevo: hecho (RESPALDADO 2", status["text"])
        self.assertIn("contradicciones internas: descartado (motivo:", status["text"])
        self.assertEqual(status["design_sources"], [self.ids()["diseno"]])
        set_language(PID, "en")
        self.assertIn("new design: done (BACKED 2", cross_status(PID, CID)["text"])

    def test_stale_when_a_cited_source_is_superseded(self):
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        ids = self.ids()
        copy = Path.cwd() / "prototipo-v2.html"
        html = (CROSSES / "prototipo-aprobaciones.html").read_text(encoding="utf-8")
        copy.write_text(html.replace("</body>", "<p>Pantalla nueva de reportes de altas</p>\n</body>"), encoding="utf-8")
        loaded = json.loads(run_ok(["sources", PID, "--load", str(copy), "--role", "diseno_nuevo", "--change", CID]))
        run_ok(["sources", PID, "--id", ids["diseno"], "--superseded-by", loaded["source_id"], "--reason", "x"])
        status = cross_status(PID, CID)
        self.assertEqual(status["kinds"]["diseno"]["state"], "stale")
        self.assertEqual(status["kinds"]["diseno"]["stale_sources"], [ids["diseno"]])
        self.assertIn("diseno", status["missing"])

    def test_fingerprint(self):
        self.assertEqual(crosses_fingerprint(PID, CID), "")
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        first = crosses_fingerprint(PID, CID)
        self.assertEqual(len(first), 12)
        self.assertEqual(crosses_fingerprint(PID, CID), first)
        skip_cross(PID, CID, "contradicciones", "El pedido es corto")
        self.assertNotEqual(crosses_fingerprint(PID, CID), first)


class BaselineWaiver(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(CROSSES / "pedido_contradiccion.md", Path.cwd() / "pedido.md")
        run_ok(["init", "SINB"])
        run_ok(["ingest", "SINB", "--source", "pedido.md", "--change"])

    def test_baseline_waiver_counts_as_waived(self):
        self.assertEqual(cross_status("SINB", CID)["kinds"]["linea_de_base"]["state"], "missing")
        run_ok(["sources", "SINB", "--change", CID, "--no-baseline", "--reason", "x"])
        kind = cross_status("SINB", CID)["kinds"]["linea_de_base"]
        self.assertEqual((kind["state"], kind["reason"]), ("waived", "x"))


if __name__ == "__main__":
    unittest.main()
