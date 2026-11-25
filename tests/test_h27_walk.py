"""IMP-406 (H27 inc 1) task 9: the whole walk with the long request, by CLI.

Fine inventory, reading plan, line coverage and partial readings, verification, the change verdict, deferred
questions and the final export in brief v2 format.
"""
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
from helpers import IDS_SCOPE_ANSWER, reproposal_block, run_cli, run_ok  # noqa: E402

from sentinel.consolidation_control import consolidation_control  # noqa: E402
from sentinel.changes import deferred_gaps  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXTRACTION = FIXTURES / "change_extraction"
CROSSES = FIXTURES / "change_crosses"
PID = "LARGO"
CID = "CHG-001"
PARTS = [f"SEC-proceso-to-be-detallado.p{n}" for n in range(1, 5)]
HEADINGS = ["## 0. Encabezado", "## 1. Overview", "## 2. Lente de Negocio", "## 3. Lente de Producto",
            "## 4. Lente de Diseño", "## 5. Lente Técnico", "## 6. Acuerdos del Release",
            "## 7. Dependencias y Cuestiones a Confirmar", "## 8. Supuestos", "## 9. Cosas a Construir"]


def cli(*argv: str) -> dict:
    return json.loads(run_ok([*argv]))


def extract(*argv: str) -> dict:
    return cli("extract", PID, "--change", CID, *argv)


def next_step() -> dict:
    return cli("next", PID, "--change", CID)


def status() -> dict:
    return cli("status", PID, "--change", CID)


def brief_section(brief: str, number: int) -> str:
    lines = brief.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"## {number}."))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


class LongRequestWalk(unittest.TestCase):
    def setUp(self):
        self.old = Path.cwd()
        self.folder = tempfile.mkdtemp(prefix="sentinel_largo_")
        os.chdir(self.folder)
        forget_read_snapshots()

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.folder, ignore_errors=True)

    def claims(self, name: str, ids: dict[str, str], drop: str = "") -> str:
        text = (CROSSES / name).read_text(encoding="utf-8")
        text = text.replace("F-PED", ids["pedido"]).replace("F-DIS", ids["diseno"])
        if drop:
            blocks = text.split("\n- [")
            text = "\n- [".join(b for b in blocks if not b.startswith(drop))
        path = Path(self.folder) / f"sub-{drop or 'full'}-{name}"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def answer(self, gap: str, text: str) -> None:
        path = Path(self.folder) / f"ans-{gap}.md"
        path.write_text("\n".join([f"### {gap}", f"- Respuesta: {text}", "- Owner / fuente: Jefa de Compras",
                                   "- Estado de decisión: confirmado", ""]), encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])

    def test_walk(self):
        root = Path(self.folder)
        shutil.copy(EXTRACTION / "pedido_largo.md", root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")

        # 1. a clean change workspace with the long request, the baseline and the prototype
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        self.assertEqual(status()["health"], "CLEAN")
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(FIXTURES / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base", "--change", CID])
        run_ok(["sources", PID, "--load", str(CROSSES / "prototipo-aprobaciones.html"),
                "--role", "diseno_nuevo", "--change", CID])
        by_role = status()["sources"]["by_role"]
        ids = {"pedido": by_role["pedido"][0], "diseno": by_role["diseno_nuevo"][0]}

        # 2. the design cross opens the three kinds of question; the other two crosses are waived
        result = cli("cross", PID, "--change", CID, "--kind", "diseno", "--claims", self.claims("cruce_diseno.md", ids))
        gaps = result["gaps_opened"]
        gap_dis = next(g for g in gaps if g.startswith("GAP-DIS-"))
        gap_srd = next(g for g in gaps if g.startswith("GAP-SRD-"))
        gap_sed = next(g for g in gaps if g.startswith("GAP-SED-"))
        cli("cross", PID, "--change", CID, "--kind", "contradicciones", "--skip", "--reason", "x")
        cli("cross", PID, "--change", CID, "--kind", "linea_de_base", "--skip", "--reason", "x")
        self.answer(gap_dis, "Rige el pedido: el umbral es 5.000.000 y el prototipo se corrige.")

        # 3. the design cross again without the claim that only the design makes: its question is retired
        result = cli("cross", PID, "--change", CID, "--kind", "diseno",
                     "--claims", self.claims("cruce_diseno.md", ids, drop="SOLO EN DISEÑO]"))
        self.assertEqual(result["retired_gaps"], [gap_sed])
        cli("self-review", PID, "--crosses", "--change", CID, "--skip", "--reason", "x")  # IMP-410: the lenses are read before the extraction

        # 4. the inventory splits the long section into four parts and plans the reading
        inventory = extract()
        self.assertEqual(inventory["split"], {"SEC-proceso-to-be-detallado": PARTS})
        self.assertEqual(status()["reading_plan"]["text"], "lote 1 de 1")

        # 5. partial proposals: the short part and the partial reading are flagged and held back
        result = extract("--proposals", str(EXTRACTION / "propuestas_largo.md"))
        self.assertIn(PARTS[1], result["flagged"])
        self.assertIn(PARTS[2], result["flagged"])
        result = extract("--confirm", "all")
        self.assertEqual(sorted(result["held"]), sorted([PARTS[1], PARTS[2], "HU-03"]))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["extract", PID, "--change", CID, "--confirm-item", PARTS[1]])
        self.assertNotEqual(code, 0)
        self.assertIn("69-78", out.getvalue() + err.getvalue())
        step = next_step()
        self.assertEqual(step["key"], "extract_confirm")
        self.assertEqual(step["title"], "Completar las lecturas parciales")
        self.assertIn(PARTS[1], step["text"])
        self.assertIn(PARTS[2], step["text"])
        self.assertNotIn("HU-03", step["text"])

        # 6. the correction completes the readings; the flagged story is confirmed by hand
        extract("--proposals", str(EXTRACTION / "propuestas_largo_fix.md"))
        result = extract("--confirm", "all")
        confirmed = json.dumps(result["confirmed"])
        self.assertIn(PARTS[1], confirmed)
        self.assertIn(PARTS[2], confirmed)
        result = extract("--confirm-item", "HU-03")
        self.assertEqual(result["coverage"]["covered"], result["coverage"]["total"])

        # 7. verification: a sample of three, one differs and goes back to proposed
        sample = extract("--verify", "--sample", "3")
        sampled = sample["sample"]
        self.assertEqual(len(sampled), 3)
        answers = root / "verificacion.md"
        answers.write_text("\n".join(["## Resultados", f"- {sampled[0]}: difiere — falta un dato",
                                      *[f"- {i}: igual" for i in sampled[1:]], ""]), encoding="utf-8")
        result = extract("--verify-result", str(answers))
        self.assertEqual(result["reopened"], [sampled[0]])
        code, _ = run_cli(["extract", PID, "--change", CID, "--confirm-item", sampled[0]])
        self.assertNotEqual(code, 0)  # the verification said it differs and nothing changed: it is not re-confirmed as is
        fixed = root / "corregido.md"
        fixed.write_text(reproposal_block(PID, CID, sampled[0]), encoding="utf-8")
        extract("--proposals", str(fixed))
        result = extract("--confirm-item", sampled[0])
        self.assertEqual(result["coverage"]["covered"], result["coverage"]["total"])

        # 8. the verdict: the open build questions hold the change back until the BA classes them
        current = status()["verdict"]
        self.assertEqual(current["verdict"], "NOT_READY")
        forget_read_snapshots()
        build = [d["id"] for d in deferred_gaps(PID, CID) if d["impact"] == "construccion"]
        self.assertIn(gap_srd, build)
        self.assertNotIn(gap_sed, build)
        for gap in build:
            run_ok(["gaps", PID, "--change", CID, "--id", gap, "--impact", "operativo",
                    "--reason", "lo resuelve el área de Compras"])
        current = status()["verdict"]
        self.assertEqual(current["verdict"], "NOT_READY")  # the brief is not compiled yet: the verdict says so (I8)
        self.assertEqual(current["blockers"], ["el brief del cambio no está compilado"])
        run_ok(["brief", PID, "--change", CID])
        current = status()["verdict"]
        self.assertEqual(current["verdict"], "READY_WITH_WARNINGS")
        self.assertEqual(current["deferred"]["construccion"], 0)
        operativo = current["deferred"]["operativo"]
        self.assertGreaterEqual(operativo, len(build))

        # 9. the brief carries the table of states as is; the next step is the final export
        base = Path("workspaces") / PID
        table = [line for line in (EXTRACTION / "pedido_largo.md").read_text(encoding="utf-8").splitlines()[84:98]]
        brief = next(base.rglob("project-brief.md")).read_text(encoding="utf-8")
        for line in table:
            self.assertIn(line, brief_section(brief, 4), line)
        # IMP-414: the answer of the design question has no option, so it changes the element it touches: the BA keeps the text
        self.assertEqual(next_step()["key"], "consolidate")
        for row in consolidation_control(PID, CID)["rows"]:
            if row["status"] == "pendiente":
                for gap in row["gaps"]:
                    extract("--keep-text", row["element"], "--gap", gap, "--reason", "el texto del pedido queda")
        self.assertEqual(next_step()["key"], "export_final")

        # 10. the final export: ten v2 headings, sealed, the table as is and the new surface marked
        run_ok(["export", PID, "--artifact", "brief", "--change", CID, "--final"])
        exported = next((base / "08_context_packs" / "exports").glob(f"{CID}-*brief*.md"))
        text = exported.read_text(encoding="utf-8")
        positions = [text.index(heading) for heading in HEADINGS]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("**Estado:** final", text)
        self.assertIn(f"**Pendientes diferidos:** {operativo} (construcción 0, operativo {operativo})", text)
        for line in table:
            self.assertIn(line, text, line)
        self.assertIn("[nuevo]", text)
        self.assertEqual(next_step()["key"], "specs")

        # 11. the workspace is clean, the verification is on record and the project path knows nothing of the change
        current = status()
        self.assertEqual(current["health"], "CLEAN")
        self.assertEqual(current["verification"]["last"]["differs"], 1)
        code, out = run_cli(["status", PID])
        self.assertEqual(code, 0)
        project = json.loads(out)
        for key in ("health_detail", "reading_plan", "verification", "final_export"):
            self.assertNotIn(key, project)
        self.assertNotEqual(project.get("verdict"), current["verdict"])


if __name__ == "__main__":
    unittest.main()
