"""IMP-402 (H26 inc 3) task 9: the whole extraction walk, by CLI, with the ids fixture."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, run_ok  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXTRACTION = FIXTURES / "change_extraction"
PID = "WALK"
CID = "CHG-001"
ACCEPTANCE_HEADING = "## Criterios de aceptación\n"
# The lens round reads the body of the request, not its headings: one line under the heading keeps GAP-ACCEPTANCE closed
# by the request itself, so the ids fixture (shared with the other extraction tests) stays untouched.
ACCEPTANCE_LINE = "Criterios de aceptación del cambio, por cada regla:\n"


def cli(*argv: str) -> dict:
    return json.loads(run_ok([*argv]))


def extract(*argv: str) -> dict:
    return cli("extract", PID, "--change", CID, *argv)


def next_step() -> dict:
    return cli("next", PID, "--change", CID)


class ExtractionWalk(unittest.TestCase):
    def setUp(self):
        self.old = Path.cwd()
        self.folder = tempfile.mkdtemp(prefix="sentinel_walk_")
        os.chdir(self.folder)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_walk(self):
        root = Path(self.folder)
        pedido = (EXTRACTION / "pedido_ids.md").read_text(encoding="utf-8")
        self.assertIn(ACCEPTANCE_HEADING, pedido)
        (root / "pedido.md").write_text(pedido.replace(ACCEPTANCE_HEADING, ACCEPTANCE_HEADING + ACCEPTANCE_LINE), encoding="utf-8")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")

        # 1. a mature request: scope answered, baseline loaded, no blocking gap left
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(FIXTURES / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base", "--change", CID])

        # 2. inventory is the next step
        self.assertEqual(next_step()["key"], "extract_inventory")

        # 3. inventory
        inventory = extract()
        self.assertEqual(inventory["total"], 22)
        self.assertEqual(inventory["by_kind"], {"section": 6, "story": 3, "rule": 6, "criterion": 5, "decision": 2})
        step = next_step()
        self.assertEqual(step["key"], "extract_proposals")
        self.assertIn("22 de 22", step["text"])

        # 4. proposals, with CA-05 quoting wrongly on purpose
        result = extract("--proposals", str(EXTRACTION / "propuestas_walk.md"))
        self.assertEqual(len(result["recorded"]), 20)
        self.assertNotIn("CA-05", result["recorded"])
        self.assertNotIn("RN-01", result["recorded"])
        self.assertIn("CA-05", json.dumps(result["rejected"]))
        self.assertIn("la cita no aparece literal", json.dumps(result["rejected"], ensure_ascii=False))  # quote_not_found
        self.assertEqual(result["flagged"], ["RN-04"])
        step = next_step()
        self.assertEqual(step["key"], "extract_proposals")
        self.assertIn("2 de 22", step["text"])

        # 5. the correction
        result = extract("--proposals", str(EXTRACTION / "propuestas_walk_fix.md"))
        self.assertEqual(result["recorded"], ["RN-01", "CA-05"])
        step = next_step()
        self.assertEqual(step["key"], "extract_confirm")
        self.assertIn("1 marcada(s)", step["text"])

        # 6. confirm one section: the flagged rule is held back
        result = extract("--confirm", "reglas-de-negocio")
        for element in ("RN-01", "RN-02", "RN-03", "RN-05", "RN-06"):
            self.assertIn(element, json.dumps(result["confirmed"]), element)
        self.assertEqual(result["held"], ["RN-04"])

        # 7. confirm everything else
        result = extract("--confirm", "all")
        self.assertEqual(result["held"], ["RN-04"])
        status = cli("status", PID, "--change", CID)
        self.assertTrue(status["extraction"]["text"].startswith("21 de 22"), status["extraction"]["text"])
        self.assertIn("Reglas 5 de 6", status["extraction"]["text"])
        self.assertEqual(status["preserved"]["missing"], [])

        # 8. reject the flagged one: it goes back to pending
        extract("--reject-item", "RN-04", "--reason", "se revisa con la jefa de Compras")
        step = next_step()
        self.assertEqual(step["key"], "extract_proposals")
        self.assertIn("1 de 22", step["text"])

        # 9. re-propose it as a discard, same flag: held by `all`, confirmed by hand
        again = root / "rn04.md"
        again.write_text(
            "### RN-04\n- Tratamiento: descarte\n"
            "- Motivo: la jefa de Compras lo resuelve fuera de este cambio\n"
            '- Cita: "La jefa de Compras no puede aprobar un alta que cargó ella misma."\n'
            "- Marca: contradiccion — el SAD permite que una jefatura apruebe sus propias altas\n",
            encoding="utf-8",
        )
        self.assertEqual(extract("--proposals", str(again))["recorded"], ["RN-04"])
        self.assertEqual(extract("--confirm", "all")["held"], ["RN-04"])
        self.assertIn("RN-04", json.dumps(extract("--confirm-item", "RN-04")["confirmed"]))

        # 10. the brief carries the extraction and its coverage
        self.assertEqual(next_step()["key"], "brief")
        run_ok(["brief", PID, "--change", CID])
        base = Path("workspaces") / PID
        brief = next(base.rglob("project-brief.md")).read_text(encoding="utf-8")
        self.assertIn("la jefatura aprueba las altas de monto alto dentro del sistema", brief)
        self.assertNotIn("PENDIENTE DE EXTRACCIÓN", brief)
        self.assertIn("Cobertura de la extracción: 22 de 22", brief)
        report = json.loads(next(base.rglob("change_brief_report.json")).read_text(encoding="utf-8"))
        self.assertIs(report["extraction"]["complete"], True)
        self.assertEqual(report["extraction_pending"], [])

        # 11. requirements: 9 current rows, 7 ADDED and 2 UNCHANGED
        requirements = next(base.rglob("requirements.md")).read_text(encoding="utf-8")
        rows = [line for line in requirements.splitlines() if line.startswith("|") and ("ADDED" in line or "UNCHANGED" in line)]
        self.assertEqual(len(rows), 9, requirements)
        self.assertEqual(sum("UNCHANGED" in r for r in rows), 2)
        self.assertEqual(sum("UNCHANGED" not in r for r in rows), 7)
        rn02 = [r for r in rows if "EXT:RN-02" in r]
        self.assertEqual(len(rn02), 2)
        self.assertNotEqual(rn02[0], rn02[1])

        # 12. specs and backlog carry the preserved rows as pass-to-pass
        run_ok(["specs", PID, "--change", CID])
        run_ok(["backlog", PID, "--change", CID])
        validation = run_ok(["validate", PID, "--change", CID])
        self.assertIn("VALID", validation)
        unchanged_ids = [r.split("|")[1].strip() for r in rows if "UNCHANGED" in r]
        self.assertEqual(len(unchanged_ids), 2)
        stories = sorted(base.rglob("US-*.md")) or sorted(p for p in base.rglob("*.md") if "backlog" in str(p).lower())
        self.assertTrue(stories)
        for story in stories:
            p2p = [line for line in story.read_text(encoding="utf-8").splitlines()
                   if line.startswith("| AC-") and "pass-to-pass" in line]
            for row_id in unchanged_ids:
                self.assertTrue(any(row_id in line for line in p2p), (story.name, row_id))
        self.assertIn("EXT:RN-01", requirements)
        self.assertIn("EXT:SEC-se-preserva", requirements)

        # 13. done
        step = next_step()
        self.assertEqual(step["key"], "done")
        self.assertIn("22 de 22", step["text"])
        run_ok(["export", PID, "--artifact", "brief", "--change", CID, "--final"])


if __name__ == "__main__":
    unittest.main()
