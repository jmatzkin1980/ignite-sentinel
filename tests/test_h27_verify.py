"""IMP-406 (H27 inc 1) task 5: verification sampling of a confirmed extraction."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, complete_extraction, run_cli, run_ok, waive_crosses  # noqa: E402

from sentinel.core.io import forget_read_snapshots, read_json  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.extraction import extraction_dir, run_extract  # noqa: E402
from sentinel.extraction.confirm import confirm_item  # noqa: E402
from sentinel.extraction.coverage import extraction_coverage  # noqa: E402
from sentinel.extraction.proposals import load_proposals  # noqa: E402
from sentinel.extraction.verify import parse_verify_results, verification_status  # noqa: E402
from sentinel.readiness_verdict import change_next_step  # noqa: E402
from sentinel.status import change_status  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LARGO = FIXTURES / "change_extraction" / "pedido_largo.md"
PID = "FIN"
CID = "CHG-001"


class Parsing(unittest.TestCase):
    def test_parse_verify_results(self):
        found, unknown = parse_verify_results(
            "- A-1: igual\n* B-2: Difiere — falta el plazo\n- C-3: same\n- D-4: DIFFERS - cambia el monto\n- E-5: \n"
            "- F-6: quizá\n")
        self.assertEqual(found["A-1"], {"verdict": "igual", "note": ""})
        self.assertEqual(found["B-2"], {"verdict": "difiere", "note": "falta el plazo"})
        self.assertEqual(found["C-3"]["verdict"], "igual")
        self.assertEqual(found["D-4"], {"verdict": "difiere", "note": "cambia el monto"})
        self.assertNotIn("E-5", found)
        self.assertEqual(unknown, ["F-6"])


class Verify(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(LARGO, root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(FIXTURES / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base", "--change", CID])
        complete_extraction(PID, CID)

    def setUp(self):
        super().setUp()
        forget_read_snapshots()  # the work folder keeps its path between tests; what an earlier test read is gone

    def proposals_bytes(self) -> bytes:
        return (extraction_dir(workspace_path(PID), CID) / "proposals.json").read_bytes()

    def runs(self) -> list[dict]:
        forget_read_snapshots()
        return read_json(extraction_dir(workspace_path(PID), CID) / "verification.json", {})["runs"]

    def results(self, sample: list[str], overrides: dict[str, str] | None = None, name: str = "results.md") -> Path:
        verdicts = {element_id: "igual" for element_id in sample} | (overrides or {})
        lines = ["## Resultados", *(f"- {i}: {v}" for i, v in verdicts.items()), ""]
        path = Path.cwd() / name
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_sample_is_reproducible(self):
        first = run_extract(PID, CID, verify=True, sample=3)
        second = run_extract(PID, CID, verify=True, sample=3)
        self.assertEqual(first["sample"], second["sample"])
        self.assertEqual(len(first["sample"]), 3)
        items = load_proposals(workspace_path(PID), CID)["items"]
        self.assertTrue(all(items[i]["status"] == "confirmed" for i in first["sample"]))
        runs = self.runs()
        self.assertEqual([r["status"] for r in runs], ["superseded", "open"])
        self.assertEqual([r["n"] for r in runs], [1, 2])
        text = Path(second["request_path"]).read_text(encoding="utf-8")
        self.assertTrue(second["request_path"].endswith("002-muestra.md"))
        for element_id in first["sample"]:
            self.assertIn(f"### {element_id}", text)
            self.assertIn(f"- {element_id}: ", text)
        self.assertIn("## Resultados", text)
        self.assertIn("texto literal", text.lower())
        self.assertIn("muestra de verificación 2 con 3 elemento(s)", second["message"])

    def test_sample_shows_rows_of_a_requirement(self):
        result = run_extract(PID, CID, verify=True, sample=26)
        text = Path(result["request_path"]).read_text(encoding="utf-8")
        self.assertIn("UNCHANGED", text)
        self.assertIn("Enunciado (fila", text)

    def test_all_same(self):
        sample = run_extract(PID, CID, verify=True, sample=3)["sample"]
        out = run_extract(PID, CID, verify_result=str(self.results(sample)))
        self.assertEqual((out["same"], out["differs"], out["reopened"]), (sorted(sample, key=sample.index), [], []))
        self.assertEqual(out["message"], f"{CID}: verificación 1: 3 igual(es), 0 difiere(n); reabiertos: —")
        last = verification_status(PID, CID)["last"]
        self.assertEqual({k: last[k] for k in ("n", "sample", "same", "differs", "reopened")},
                         {"n": 1, "sample": 3, "same": 3, "differs": 0, "reopened": []})
        self.assertTrue(last["completed_at"])
        self.assertEqual(self.runs()[0]["status"], "done")
        self.assertFalse(verification_status(PID, CID)["open"])

    def test_differs_reopens(self):
        sample = run_extract(PID, CID, verify=True, sample=3)["sample"]
        target = sample[0]
        before = extraction_coverage(PID, CID)["covered"]
        out = run_extract(PID, CID, verify_result=str(
            self.results(sample, {target: "difiere — falta el plazo de 3 días hábiles"})))
        self.assertEqual((out["differs"], out["reopened"]), ([target], [target]))
        self.assertIn(f"reabiertos: {target}", out["message"])
        forget_read_snapshots()
        item = load_proposals(workspace_path(PID), CID)["items"][target]
        self.assertEqual((item["status"], item["confirmed_at"]), ("proposed", None))
        marks = [f for f in item["flags"] if f["kind"] == "verificacion_difiere"]
        self.assertEqual(marks, [{"origin": "verify", "kind": "verificacion_difiere", "ref": "verify:1",
                                  "note": "falta el plazo de 3 días hábiles"}])
        self.assertEqual(extraction_coverage(PID, CID)["covered"], before - 1)
        self.assertEqual(change_next_step(PID, CID)["key"], "extract_confirm")
        confirm_item(PID, CID, target)
        forget_read_snapshots()
        self.assertEqual(load_proposals(workspace_path(PID), CID)["items"][target]["status"], "confirmed")
        self.assertEqual(extraction_coverage(PID, CID)["covered"], before)
        last = verification_status(PID, CID)["last"]
        self.assertEqual((last["same"], last["differs"], last["reopened"]), (2, 1, [target]))

    def test_bad_results_change_nothing(self):
        with self.assertRaises(InputError) as caught:  # no open run
            run_extract(PID, CID, verify_result=str(self.results(["RN-01"])))
        self.assertIn(f"No hay una verificación abierta en {CID}", str(caught.exception))
        self.assertIn("--verify", str(caught.exception))
        sample = run_extract(PID, CID, verify=True, sample=3)["sample"]
        outside = next(i for i in ("RN-01", "RN-02", "CA-01", "PD-01") if i not in sample)
        before = self.proposals_bytes()
        cases = {
            f"{outside} no está en la muestra de la verificación 1": self.results(sample, {outside: "igual"}, "a.md"),
            "faltan resultados para: " + sample[-1]: self.results(sample[:-1], None, "b.md"),
            f"{sample[0]}: «difiere» necesita una nota": self.results(sample, {sample[0]: "difiere"}, "c.md"),
        }
        for message, path in cases.items():
            with self.assertRaises(InputError) as caught:
                run_extract(PID, CID, verify_result=str(path))
            self.assertIn(message, str(caught.exception))
            self.assertEqual(self.proposals_bytes(), before)
        self.assertEqual(self.runs()[0]["status"], "open")

    def test_nothing_confirmed_and_bad_sample(self):
        with self.assertRaises(InputError) as caught:
            run_extract(PID, CID, verify=True, sample=0)
        self.assertEqual(str(caught.exception), "--sample debe ser 1 o más")
        with patch("sentinel.extraction.verify.load_proposals", lambda base, cid: {"items": {}}):
            with self.assertRaises(InputError) as caught:
                run_extract(PID, CID, verify=True)
        self.assertEqual(str(caught.exception), f"{CID} no tiene elementos confirmados para verificar")

    def test_verification_warning(self):
        from sentinel.extraction import coverage

        real = coverage.extraction_coverage

        def big(project_id, change_id):
            return {**real(project_id, change_id), "total": 150}

        with patch("sentinel.extraction.coverage.extraction_coverage", big):
            warnings = change_status(PID, CID)["warnings"]
        found = [w for w in warnings if w["trigger"] == "verification_missing"]
        self.assertEqual(len(found), 1, warnings)
        self.assertIn("150 elementos y no se verificó ninguna muestra", found[0]["message"])
        self.assertIn(f"/extract {PID} --change {CID} --verify", found[0]["message"])
        self.assertEqual(change_status(PID, CID)["verification"], {"runs": 0, "open": False, "last": None})
        sample = run_extract(PID, CID, verify=True, sample=2)["sample"]
        run_extract(PID, CID, verify_result=str(self.results(sample)))
        with patch("sentinel.extraction.coverage.extraction_coverage", big):
            warnings = change_status(PID, CID)["warnings"]
        self.assertEqual([w for w in warnings if w["trigger"] == "verification_missing"], [])

    def test_cli_and_mcp(self):
        out = json.loads(run_ok(["extract", PID, "--change", CID, "--verify", "--sample", "2"]))
        self.assertEqual((out["action"], len(out["sample"])), ("verify", 2))
        for argv in (["--sample", "2"], ["--verify", "--confirm", "all"], ["--verify", "--verify-result", "x.md"]):
            code, _ = run_cli(["extract", PID, "--change", CID, *argv])
            self.assertNotEqual(code, 0, argv)
        from tests.test_mcp_change import _argv

        self.assertEqual(
            _argv("sentinel_extract", project_id=PID, change=CID, verify=True, sample=2),
            ["extract", PID, "--change", CID, "--verify", "--sample", "2"])
        self.assertEqual(
            _argv("sentinel_extract", project_id=PID, change=CID, verify_result="r.md"),
            ["extract", PID, "--change", CID, "--verify-result", "r.md"])


if __name__ == "__main__":
    unittest.main()
