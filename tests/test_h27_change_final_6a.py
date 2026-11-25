"""IMP-418 (H27 inc 6a) final review wave: request edited in place, refusal language, --supersedes reused, scoped scan and rebase."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots, read_json  # noqa: E402
from sentinel.crosses import cross_path, run_cross  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.crosses.state import cross_status  # noqa: E402
from sentinel.extraction.inventory import _row_path  # noqa: E402
from sentinel.sources import load_source_manifest  # noqa: E402
from sentinel.status import change_status  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

PID = "TCFN"
CID = "CHG-001"
RN07 = "| RN-07 | Un alta de un proveedor ya inactivo se reactiva con aprobación de la jefa de Compras. |\n"
RN06 = "| RN-06 | Los proveedores del exterior quedan fuera de este cambio. |\n"
DIVERGENCE_V2 = "\n".join([
    "# Cruce delta",
    "",
    "- [DIVERGENCIA] El pedido fija el umbral en 3.000.000 y el prototipo muestra 1.000.000.",
    '  - Pedido: F-V2 "mayor a 3.000.000 requiere aprobación de la jefa de Compras"',
    '  - Diseño: F-DIS "Umbral de aprobación: 1.000.000"',
    "",
])


def fails(argv: list[str]) -> tuple[int, str]:
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


class FinalCase(SyncCase):
    PID = PID

    def sync(self, *extra: str) -> dict:
        out = run_ok(["sync", PID, "--change", CID, *extra])
        forget_read_snapshots()
        return json.loads(out)

    def row(self, source_id: str) -> dict:
        return next(r for r in load_source_manifest(PID)["registry"] if r["id"] == source_id)

    def record(self, kind: str) -> dict:
        return read_json(cross_path(workspace_path(PID), CID, kind), {})

    def set_language(self, language: str, change: str = CID) -> None:
        changes = {key: dict(value) for key, value in list_changes(PID).items()}
        changes[change]["language"] = language
        update_state(PID, changes=changes)
        forget_read_snapshots()

    def v2(self) -> Path:
        Path("v2").mkdir(exist_ok=True)
        return self.write_v2("v2/pedido.md")

    def second_change(self) -> str:
        Path("otro.md").write_text("# Otro pedido\n\nQueremos un reporte mensual de las altas rechazadas.\n", encoding="utf-8")
        run_ok(["ingest", PID, "--source", "otro.md", "--change"])
        forget_read_snapshots()
        return next(c for c in list_changes(PID) if c != CID)


class InPlaceEdit(FinalCase):
    """I1: the request copy edited in place keeps no old text: every element of the new source is new."""

    def test_inplace_edit_writes_the_delta(self):
        old = self.ids()["pedido"]
        copy = Path.cwd() / _row_path(self.row(old))
        text = copy.read_text(encoding="utf-8")
        self.assertIn(RN06, text)
        copy.write_text(text.replace(RN06, RN06 + RN07), encoding="utf-8")
        scanned = self.sync()
        loaded = scanned["loaded"][0]
        self.assertEqual(loaded["version_of"], old)
        self.assertIs(loaded["confirmed"], False)
        new = loaded["source_id"]
        out = json.loads(run_ok(["sources", PID, "--id", old, "--superseded-by", new, "--reason", "v2 en el lugar"]))
        forget_read_snapshots()
        self.assertTrue(any("RN-07" in i for i in out["sync"][0]["extraction"]["new"]))
        kinds = cross_status(PID, CID)["kinds"]
        self.assertTrue(kinds["diseno"]["delta"])
        self.assertTrue(kinds["contradicciones"]["delta"])
        self.assertEqual(kinds["diseno"]["state"], "stale")
        self.assertEqual(kinds["contradicciones"]["state"], "stale")
        self.assertTrue(self.record("diseno")["pending_delta"]["elements"])
        report = (workspace_path(PID) / "01_discovery" / CID / "sync_report.md").read_text(encoding="utf-8")
        self.assertIn("se editó en el lugar", report)

    def test_a_version_in_its_own_file_still_diffs(self):
        old = self.ids()["pedido"]
        out = self.sync("--source", str(self.v2()), "--role", "pedido", "--supersedes", old)
        extraction = out["sync"][0]["extraction"]
        self.assertEqual(len(extraction["changed"]), 1)
        self.assertEqual(extraction["new"], [])


class RefusalLanguage(FinalCase):
    """M2: the refusals follow the language of the change."""

    @classmethod
    def build_workspace(cls) -> None:
        super().build_workspace()

    def payload(self) -> str:
        path = Path.cwd() / "p.json"
        path.write_text(json.dumps({"gaps": [], "absent": [], "untouched": [], "ambiguities": [], "assumptions": []}),
                        encoding="utf-8")
        return str(path)

    def test_anchors_with_change_in_english(self):
        self.set_language("en")
        code, err = fails(["scrutinize", PID, "--source", self.payload(), "--change", CID, "--mode", "anchors"])
        self.assertNotEqual(code, 0)
        self.assertNotIn("usá", err)
        self.assertIn("--mode anchors", err)
        self.assertIn(f"--change {CID}", err)
        self.assertIn("FILE", err)

    def test_probe_with_change_in_english(self):
        self.set_language("en")
        code, err = fails(["scrutinize", PID, "--source", self.payload(), "--change", CID,
                           "--mode", "implementability-probe"])
        self.assertNotEqual(code, 0)
        self.assertNotIn("usá", err)
        self.assertIn("implementability-probe", err)
        self.assertIn("FILE", err)

    def test_probe_and_anchors_stay_spanish_in_a_spanish_change(self):
        for mode in ("anchors", "implementability-probe"):
            code, err = fails(["scrutinize", PID, "--source", self.payload(), "--change", CID, "--mode", mode])
            self.assertNotEqual(code, 0, mode)
            self.assertIn("usá", err, mode)
            self.assertIn("ARCHIVO", err, mode)

    def test_delta_without_claims_follows_the_language(self):
        with self.assertRaises(ValueError) as ctx:
            run_cross(PID, CID, delta=True)
        self.assertIn("--delta va con --claims", str(ctx.exception))
        self.set_language("en")
        with self.assertRaises(ValueError) as ctx:
            run_cross(PID, CID, delta=True)
        self.assertIn("--delta goes with --claims", str(ctx.exception))


class ChangeOnlyLanguage(unittest.TestCase):
    """M2: a workspace that only holds changes refuses the project form in the language of its first change."""

    def setUp(self) -> None:
        import os
        import shutil
        import tempfile

        self.previous = os.getcwd()
        self.folder = tempfile.mkdtemp()
        os.chdir(self.folder)
        self._shutil = shutil
        pedido = Path(__file__).resolve().parent / "fixtures" / "change_crosses" / "pedido_contradiccion.md"
        shutil.copy(pedido, "pedido.md")
        run_ok(["init", "TCFO"])
        run_ok(["ingest", "TCFO", "--source", "pedido.md", "--change"])

    def tearDown(self) -> None:
        import os

        os.chdir(self.previous)
        self._shutil.rmtree(self.folder, ignore_errors=True)

    def test_english_change_gets_english_refusal(self):
        changes = {key: dict(value) for key, value in list_changes("TCFO").items()}
        changes[CID]["language"] = "en"
        update_state("TCFO", changes=changes)
        forget_read_snapshots()
        Path("p.json").write_text("{}", encoding="utf-8")
        for command in ("challenge", "annotate", "scrutinize"):
            code, err = fails([command, "TCFO", "--source", "p.json"])
            self.assertNotEqual(code, 0, command)
            self.assertIn("only holds changes", err, command)
            self.assertNotIn("sólo", err, command)
            self.assertIn("FILE", err, command)
            self.assertIn(f"--change {CID}", err, command)


class ProjectScrutinizeKeyOrder(unittest.TestCase):
    """M1: the project /scrutinize result keeps the key order of 9f776c1."""

    def setUp(self) -> None:
        import os
        import tempfile

        self.previous = os.getcwd()
        self.folder = tempfile.mkdtemp()
        os.chdir(self.folder)

    def tearDown(self) -> None:
        import os
        import shutil

        os.chdir(self.previous)
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_key_order(self):
        quote = "El equipo de Compras quiere ordenar el alta de proveedores en el sistema."
        Path("raw.md").write_text(f"# Alta de proveedores\n\n{quote}\n", encoding="utf-8")
        run_ok(["init", "TCFK"])
        run_ok(["ingest", "TCFK", "--source", "raw.md"])
        finding = {"id": "GAP-APROBACION-AUSENCIA", "lens": "business", "severity": "high", "technique": "pre-mortem",
                   "finding_type": "domain-conflict",
                   "question": "¿Quién aprueba un alta de monto alto cuando la jefa de Compras está ausente?",
                   "evidence": quote}
        Path("s.json").write_text(json.dumps({"gaps": [finding], "absent": [], "untouched": [],
                                              "ambiguities": [], "assumptions": []}), encoding="utf-8")
        result = json.loads(run_ok(["scrutinize", "TCFK", "--source", "s.json", "--lens", "business"]))
        self.assertEqual(list(result), ["project_id", "mode", "path", "report", "knowledge_state", "merged",
                                        "skipped_duplicates", "gap_counts", "scrutiny_id", "scrutiny_report"])


class SupersedesReused(FinalCase):
    """M3: --supersedes with the content already loaded says nothing new and confirms nothing twice."""

    def test_same_content_as_the_old_row(self):
        old = self.ids()["pedido"]
        Path("copia.md").write_text((self.FIXTURES / "change_crosses" / "pedido_contradiccion.md").read_text(encoding="utf-8"),
                                    encoding="utf-8")
        out = self.sync("--source", "copia.md", "--role", "pedido", "--supersedes", old)
        loaded = out["loaded"][0]
        self.assertIs(loaded["reused"], True)
        self.assertEqual(loaded["source_id"], old)
        self.assertIs(loaded["confirmed"], False)
        self.assertEqual(out["sync"], [])
        self.assertEqual(self.row(old).get("validity", "current"), "current")

    def test_already_superseded_row_confirms_nothing(self):
        old = self.ids()["pedido"]
        v2 = self.v2()
        first = self.sync("--source", str(v2), "--role", "pedido", "--supersedes", old)
        self.assertIs(first["loaded"][0]["confirmed"], True)
        again = self.sync("--source", str(v2), "--role", "pedido", "--supersedes", old)
        self.assertIs(again["loaded"][0]["reused"], True)
        self.assertIs(again["loaded"][0]["confirmed"], False)
        self.assertEqual(again["sync"], [])


class ScopedScan(FinalCase):
    """M4: the scan skips a file that belongs to another change."""

    def test_scan_skips_files_of_another_change(self):
        other = self.second_change()
        folder = workspace_path(PID) / "00_raw" / "08_new_design"
        mine = folder / "pantalla-otro.md"
        mine.write_text("# Pantalla de reportes\n\nEl reporte mensual lista las altas rechazadas.\n", encoding="utf-8")
        loaded = json.loads(run_ok(["sources", PID, "--load", str(mine), "--role", "diseno_nuevo", "--change", other]))
        forget_read_snapshots()
        self.assertIn(loaded["source_id"], list_changes(PID)[other]["sources"])
        mine.write_text("# Pantalla de reportes\n\nEl reporte mensual lista las altas rechazadas y su motivo.\n",
                        encoding="utf-8")
        out = self.sync()
        self.assertEqual(out["loaded"], [])
        self.assertNotIn(loaded["source_id"], list_changes(PID)[CID]["sources"])

    def test_scan_still_loads_an_unregistered_file(self):
        self.second_change()
        folder = workspace_path(PID) / "00_raw" / "08_new_design"
        (folder / "pantalla-nueva.md").write_text("# Pantalla\n\nLa bandeja muestra el estado de cada alta.\n", encoding="utf-8")
        out = self.sync()
        self.assertEqual(len(out["loaded"]), 1)
        self.assertIn(out["loaded"][0]["source_id"], list_changes(PID)[CID]["sources"])

    def test_scan_wording_names_the_shared_folders(self):
        root = Path(__file__).resolve().parent.parent
        for name in ("user_guide/01-command-reference.md", "user_guide/03-workflows.md", "user_guide/11-chat-commands.md",
                     ".claude/skills/sentinel-sync/SKILL.md"):
            text = (root / name).read_text(encoding="utf-8")
            self.assertNotIn("the change's folders", text, name)
            self.assertNotIn("los directorios del cambio", text, name)


class RebaseScope(FinalCase):
    """M5: a claim is rebased only onto the change's own sources."""

    def test_foreign_prototype_does_not_carry_a_claim(self):
        other = self.second_change()
        html = (self.FIXTURES / "change_crosses" / "prototipo-aprobaciones.html").read_text(encoding="utf-8")
        foreign = Path.cwd() / "prototipo-ajeno.html"
        foreign.write_text(html.replace("</body>", "<p>Pantalla de reportes de altas</p>\n</body>"), encoding="utf-8")
        run_ok(["sources", PID, "--load", str(foreign), "--role", "diseno_nuevo", "--change", other])
        forget_read_snapshots()
        old = self.ids()["diseno"]
        mine = Path.cwd() / "prototipo-v2.html"
        mine.write_text(html.replace("Delegar aprobaciones", "Reemplazos"), encoding="utf-8")
        out = self.sync("--source", str(mine), "--role", "diseno_nuevo", "--supersedes", old)
        info = out["sync"][0]["crosses"]["diseno"]
        self.assertIn(4, info["touched"])
        self.assertNotIn(4, info["carried"])


class ReplacedGaps(FinalCase):
    """M6: an answered question of a replaced claim is reported as replaced, not withdrawn."""

    def delta(self) -> tuple[str, dict]:
        old = self.ids()["pedido"]
        out = self.sync("--source", str(self.v2()), "--role", "pedido", "--supersedes", old)
        new = out["loaded"][0]["source_id"]
        before = self.record("diseno")
        gap = next(c["gap"] for c in before["claims"] if c["tag"] == "divergencia")
        path = Path.cwd() / "delta.md"
        path.write_text(DIVERGENCE_V2.replace("F-V2", new).replace("F-DIS", self.ids()["diseno"]), encoding="utf-8")
        forget_read_snapshots()
        return gap, record_cross(PID, CID, "diseno", path, delta=True)

    def test_answered_gap_is_replaced_not_withdrawn(self):
        gap, result = self.delta()
        self.assertEqual(result["retired_gaps"], [])
        self.assertEqual(result["replaced_gaps"], [gap])
        self.assertEqual(self.record("diseno")["replaced_gaps"], [gap])
        self.assertNotIn("retired_gaps", self.record("diseno"))
        report = Path(result["report_path"]).read_text(encoding="utf-8")
        self.assertNotIn("retiradas", report)
        self.assertIn("reemplazadas", report)
        self.assertIn(gap, report)

    def test_report_in_english(self):
        self.set_language("en")
        gap, result = self.delta()
        report = Path(result["report_path"]).read_text(encoding="utf-8")
        self.assertNotIn("withdrawn", report)
        self.assertIn("replaced claims", report)
        self.assertIn(gap, report)


class StatusVersionNote(FinalCase):
    """M7: /status --change names an unconfirmed version once."""

    def test_status_names_it_once(self):
        old = self.ids()["pedido"]
        new = self.sync("--source", str(self.v2()), "--role", "pedido")["loaded"][0]["source_id"]
        status = change_status(PID, CID)
        self.assertFalse([w for w in status["warnings"] if w.get("trigger") == "unconfirmed_version"])
        shown = [w for w in [*status["warnings"], *status["verdict"]["warnings"]] if new in str(w) and old in str(w)]
        self.assertEqual(len(shown), 1)
        self.assertIn(new, status["next_step"])


if __name__ == "__main__":
    unittest.main()
