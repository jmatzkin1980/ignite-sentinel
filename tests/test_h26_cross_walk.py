"""IMP-404 (H26 inc 4) task 8: the whole cross-read walk, by CLI, with the contradictory request and the prototype."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, run_cli, run_ok  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.cli import main  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CROSSES = FIXTURES / "change_crosses"
PID = "XWALK"
CID = "CHG-001"

HU03 = "\n".join([
    "### HU-03",
    "- Tratamiento: requisito",
    '- Cita: "quiero consultar quién aprobó cada alta y cuándo"',
    "- Enunciado: Cuando el auditor consulta un alta aprobada, el sistema debe mostrar quién la aprobó y cuándo.",
    "  - Delta: ADDED",
    "  - Superficie: Historial de aprobaciones",
    "",
])


def cli(*argv: str) -> dict:
    return json.loads(run_ok([*argv]))


def cross(*argv: str) -> dict:
    return cli("cross", PID, "--change", CID, *argv)


def next_step() -> dict:
    return cli("next", PID, "--change", CID)


def status() -> dict:
    return cli("status", PID, "--change", CID)


def answer(path: Path, gap: str, text: str) -> None:
    path.write_text("\n".join([f"### {gap}", f"- Respuesta: {text}", "- Owner / fuente: Jefa de Compras",
                               "- Estado de decisión: confirmado", ""]), encoding="utf-8")
    run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])


def brief_section(brief: str, number: int) -> str:
    lines = brief.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"## {number}."))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


class CrossWalk(unittest.TestCase):
    def setUp(self):
        self.old = Path.cwd()
        self.folder = tempfile.mkdtemp(prefix="sentinel_xwalk_")
        os.chdir(self.folder)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.folder, ignore_errors=True)

    def claims(self, name: str, ids: dict[str, str]) -> str:
        text = (CROSSES / name).read_text(encoding="utf-8")
        text = text.replace("F-PED", ids["pedido"]).replace("F-DIS", ids["diseno"])
        path = Path(self.folder) / f"sub-{name}"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_walk(self):
        root = Path(self.folder)
        shutil.copy(CROSSES / "pedido_contradiccion.md", root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")

        # 1. a mature request with its baseline and its prototype loaded
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(FIXTURES / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base", "--change", CID])
        run_ok(["sources", PID, "--load", str(CROSSES / "prototipo-aprobaciones.html"),
                "--role", "diseno_nuevo", "--change", CID])
        by_role = status()["sources"]["by_role"]
        ids = {"pedido": by_role["pedido"][0], "diseno": by_role["diseno_nuevo"][0]}

        # 2. the three cross-reads are the next step
        step = next_step()
        self.assertEqual(step["key"], "crosses")
        for text in ("línea de base", "diseño nuevo", "contradicciones"):
            self.assertIn(text, step["text"])

        # 3. the baseline cross is the harvest
        run_ok(["harvest", PID, "--source", str(CROSSES / "harvest_compras.md"), "--change", CID])
        step = next_step()
        self.assertEqual(step["key"], "crosses")
        self.assertNotIn("/harvest", step["text"])
        current = status()
        self.assertEqual(current["crosses"]["kinds"]["linea_de_base"]["state"], "done")
        found = current["new_surface_candidates"]
        self.assertEqual(len(found), 2)

        # 4. design cross: three new questions, one of them blocking
        result = cross("--kind", "diseno", "--claims", self.claims("cruce_diseno.md", ids))
        self.assertEqual(len(result["gaps_opened"]), 3)
        gap_dis = next(g for g in result["gaps_opened"] if g.startswith("GAP-DIS-"))
        step = next_step()
        self.assertEqual(step["key"], "lenses")
        self.assertIn("1 gap(s) bloqueante(s)", step["text"])

        # 5. internal contradictions cross
        result = cross("--kind", "contradicciones", "--claims", self.claims("cruce_contradicciones.md", ids))
        gap_con = next(g for g in result["gaps_opened"] if g.startswith("GAP-CON-"))
        step = next_step()
        self.assertEqual(step["key"], "lenses")
        self.assertIn("2 gap(s) bloqueante(s)", step["text"])

        # 6. the BA answers both with confirmed decisions
        answer(root / "dis.md", gap_dis, "Rige el pedido: el umbral es 5.000.000 y el prototipo se corrige.")
        step = next_step()
        self.assertEqual(step["key"], "lenses")
        self.assertIn("1 gap(s) bloqueante(s)", step["text"])
        answer_con = "Rige RN-04: la jefa nunca aprueba sus propias altas; PD-03 sale del pedido."
        answer(root / "con.md", gap_con, answer_con)
        step = next_step()
        self.assertEqual(step["key"], "cross_new_surfaces")
        for item in found:
            self.assertIn(item["id"], step["text"])

        # 7. one candidate declined, the other becomes a surface of the border
        tray = next(i for i in found if "bandeja" in i["text"].lower())
        history = next(i for i in found if "historial" in i["text"].lower())
        cross("--decline-new", tray["id"], "--reason", "ya está en el borde como Bandeja de aprobaciones")
        cross("--accept-new", history["id"], "--type", "pantalla", "--name", "Historial de aprobaciones")
        border = list_changes(PID)[CID]["border"]
        self.assertEqual(len(border), 7, [b.get("name") for b in border])
        self.assertIn("Historial de aprobaciones", [b.get("name") for b in border])
        self.assertEqual(next_step()["key"], "extract_inventory")

        # 8. extraction: the new surface can be cited, the open GAP-SRD flags the requirement
        inventory = cli("extract", PID, "--change", CID)
        self.assertEqual(inventory["total"], 23)
        self.assertEqual(inventory["by_kind"]["decision"], 3)
        proposals = root / "hu03.md"
        proposals.write_text(HU03, encoding="utf-8")
        result = cli("extract", PID, "--change", CID, "--proposals", str(proposals))
        self.assertEqual(result["flagged"], ["HU-03"])
        result = cli("extract", PID, "--change", CID, "--confirm", "all")
        self.assertEqual(result["held"], ["HU-03"])

        # 9. the brief carries the crosses, the accepted surface and the contradiction decision
        run_ok(["brief", PID, "--change", CID])
        base = Path("workspaces") / PID
        brief = next(base.rglob("project-brief.md")).read_text(encoding="utf-8")
        self.assertIn("Cruces: línea de base: hecho", brief_section(brief, 1))
        self.assertIn("pantalla — Historial de aprobaciones", brief_section(brief, 3))
        self.assertIn(answer_con, brief_section(brief, 7))
        report = json.loads(next(base.rglob("change_brief_report.json")).read_text(encoding="utf-8"))
        self.assertTrue(report["crosses_fingerprint"])

        # 10. a done cross cannot be skipped; the project path knows nothing of crosses
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = main(["cross", PID, "--change", CID, "--kind", "contradicciones", "--skip", "--reason", "x"])
        self.assertNotEqual(code, 0)
        self.assertRegex(err.getvalue(), r"(?i)ya est[aá] hecho")
        code, out = run_cli(["status", PID])
        self.assertEqual(code, 0)
        self.assertNotIn("crosses", json.loads(out))
        folders = [p for p in base.rglob("crosses") if p.is_dir()]
        self.assertTrue(folders)
        for folder in folders:
            self.assertEqual(folder.parent.as_posix().split("/")[-2:], ["01_discovery", CID], folder)


if __name__ == "__main__":
    unittest.main()
