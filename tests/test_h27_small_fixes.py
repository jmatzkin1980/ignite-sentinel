"""IMP-408 (H27 inc 2) task 3: own-version option D, the request under 09_request, answer re-runs."""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, run_cli, run_ok  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.changes import list_changes  # noqa: E402
from sentinel.source_versions import check_change_versions  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
IDS = FIXTURES / "change_extraction" / "pedido_ids.md"
VERSIONS = FIXTURES / "change_versions"
PID = "H27S"
OWN = "brief-compras-r2-v6.md"
PREVIOUS = "brief-compras-r2-v5.md"


def request_text(citation: str) -> str:
    return ("# Pedido: aprobación de altas de proveedores por monto\n"
            "El alta de proveedores pasa por una aprobación según el monto de la primera compra.\n"
            f"- Pedido anterior: {citation}\n")


def gaps_text() -> str:
    return (workspace_path(PID) / "01_discovery" / "CHG-001" / "gaps.md").read_text(encoding="utf-8")


def manifest_rows() -> list[dict]:
    path = workspace_path(PID) / "00_raw" / "source_manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))["registry"]


class TempCase(unittest.TestCase):
    def setUp(self):
        self.old = Path.cwd()
        self.temp = Path(tempfile.mkdtemp(prefix="sentinel_h27_small_"))
        os.chdir(self.temp)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.temp, ignore_errors=True)


class OwnVersion(TempCase):
    def start(self, citation: str) -> None:
        (self.temp / OWN).write_text(request_text(citation), encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", OWN, "--change"])

    def test_request_citing_its_previous_version_offers_d(self):
        self.start(PREVIOUS)
        (self.temp / "brief-compras-r1.md").write_text(
            "# Brief del release 1\nAlta de proveedores con validación de CUIT.\n", encoding="utf-8")
        run_ok(["sources", PID, "--load", "brief-compras-r1.md", "--role", "plan_previo", "--change", "CHG-001"])
        text = gaps_text()
        self.assertIn("GAP-VER-", text)
        self.assertIn("(D) es una versión anterior del propio pedido: no se compara con `brief-compras-r1.md`.", text)
        self.assertIn(f"`{OWN}`", text)
        gap_id = re.search(r"GAP-VER-[A-Z0-9]+", text).group(0)
        answer = [f"### {gap_id}", "- Opción: D",
                  "- Respuesta: Es la versión anterior del propio pedido, ya reemplazada.",
                  "- Owner / fuente: Jefa de Compras", "- Estado de decisión: confirmado", ""]
        (self.temp / "respuestas.md").write_text("\n".join(answer), encoding="utf-8")
        out = json.loads(run_ok(["resolve-gaps", PID, "--source", "respuestas.md", "--change", "CHG-001"]))
        self.assertIn(gap_id, out["closed"])

    def test_request_citing_itself_or_only_itself(self):
        self.start(PREVIOUS)
        result = check_change_versions(PID, "CHG-001")
        self.assertEqual(result["opened"], [])
        self.assertEqual(result["self_version"], [{"cited": PREVIOUS, "line": 3, "pedido": OWN}])
        shutil.rmtree(self.temp / "workspaces")
        self.start(OWN)
        result = check_change_versions(PID, "CHG-001")
        self.assertEqual([m["cited"] for m in result["matched"]], [OWN])
        self.assertEqual(result["opened"], [])
        self.assertNotIn("GAP-VER-", gaps_text())

    def test_version_gap_without_self_family_unchanged(self):
        shutil.copy(VERSIONS / "pedido_con_citas.md", self.temp / "pedido.md")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["sources", PID, "--load", str(VERSIONS / "sad-compras-v2.md"), "--role", "linea_de_base", "--change", "CHG-001"])
        text = gaps_text()
        self.assertIn("GAP-VER-", text)
        self.assertNotIn("(D)", text)


class WithIdsRequest(TempCase):
    def setUp(self):
        super().setUp()
        shutil.copy(IDS, self.temp / "pedido_ids.md")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido_ids.md", "--change"])


class RequestFolder(WithIdsRequest):
    def test_ingest_change_stores_request_under_09_request(self):
        raw = workspace_path(PID) / "00_raw"
        self.assertTrue((raw / "09_request" / "pedido_ids.md").is_file())
        self.assertFalse((raw / "pedido_ids.md").exists())
        self.assertEqual(list_changes(PID)["CHG-001"]["source"], "00_raw/09_request/pedido_ids.md")
        run_ok(["sources", PID, "--load", "pedido_ids.md", "--role", "pedido", "--change", "CHG-001"])
        status = json.loads(run_ok(["status", PID, "--change", "CHG-001"]))
        self.assertEqual(len(status["sources"]["by_role"]["pedido"]), 1)

    def test_old_workspace_root_copy_still_reads(self):
        raw = workspace_path(PID) / "00_raw"
        shutil.move(str(raw / "09_request" / "pedido_ids.md"), str(raw / "pedido_ids.md"))
        state_file = workspace_path(PID) / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["changes"]["CHG-001"]["source"] = "00_raw/pedido_ids.md"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        run_ok(["gaps", PID, "--change", "CHG-001"])
        run_ok(["extract", PID, "--change", "CHG-001"])
        err = io.StringIO()
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(err):
            code = main(["ingest", PID, "--source", "pedido_ids.md", "--change"])
        self.assertNotEqual(code, 0)
        self.assertIn("ya está abierto como CHG-001", out.getvalue() + err.getvalue())


class AnswerReruns(WithIdsRequest):
    def resolve(self, text: str) -> dict:
        (self.temp / "respuestas.md").write_text(text, encoding="utf-8")
        return json.loads(run_ok(["resolve-gaps", PID, "--source", "respuestas.md", "--change", "CHG-001"]))

    @staticmethod
    def block(gap_id: str, answer: str) -> str:
        return (f"### {gap_id}\n- Respuesta: {answer}\n- Owner / fuente: Jefa de Compras\n"
                "- Estado de decisión: confirmado\n")

    def test_answer_rerun_closes_the_chain(self):
        state_file = workspace_path(PID) / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["project_language"] = "es"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        first = self.resolve(IDS_SCOPE_ANSWER)
        self.assertIsNone(first["rerun_of"])
        second_text = IDS_SCOPE_ANSWER + self.block("GAP-OBJECTIVE", "Aprobar altas de proveedores por monto.")
        second = self.resolve(second_text)
        third = self.resolve(second_text + self.block("GAP-USERS", "Analistas de Compras y la Jefa de Compras."))
        rows = [r for r in manifest_rows() if r.get("events") and r["events"][0].get("via") == "gap_resolved"]
        self.assertEqual(len(rows), 3)
        self.assertIsNone(rows[1]["pending_version_of"])
        self.assertIsNone(rows[2]["pending_version_of"])
        self.assertEqual(rows[1]["rerun_of"], rows[0]["id"])
        self.assertEqual(rows[2]["rerun_of"], rows[1]["id"])
        self.assertEqual((second["rerun_of"], third["rerun_of"]), (rows[0]["id"], rows[1]["id"]))
        log = (workspace_path(PID) / "07_changes" / "source_log.md").read_text(encoding="utf-8")
        self.assertIn("nueva corrida de F-", log)
        self.assertNotIn("posible versión nueva de", log)

    def test_failed_rerun_leaves_no_row(self):
        self.resolve(IDS_SCOPE_ANSWER)
        before = len(manifest_rows())
        bad = IDS_SCOPE_ANSWER.replace("- Borde:\n", "- Borde:\n  - nuevo | pantallita | X\n")
        (self.temp / "respuestas.md").write_text(bad, encoding="utf-8")
        code, _out = run_cli(["resolve-gaps", PID, "--source", "respuestas.md", "--change", "CHG-001"])
        self.assertEqual(code, 3)
        self.assertEqual(len(manifest_rows()), before)

    def test_other_sources_keep_the_candidate(self):
        sad = self.temp / "sad.md"
        sad.write_text("# SAD compras\nAlta de proveedores.\n", encoding="utf-8")
        run_ok(["sources", PID, "--load", "sad.md", "--role", "linea_de_base", "--change", "CHG-001"])
        sad.write_text("# SAD compras\nAlta de proveedores, versión nueva.\n", encoding="utf-8")
        run_ok(["sources", PID, "--load", "sad.md", "--role", "linea_de_base", "--change", "CHG-001"])
        row = manifest_rows()[-1]
        self.assertTrue(row["pending_version_of"])
        self.assertNotIn("rerun_of", row)


if __name__ == "__main__":
    unittest.main()
