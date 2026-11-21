"""IMP-384: the harvest inventory accepts `doc:` and the functional blocks B6-B8."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.harvest import BLOCK_PLACES, parse_harvest

DOC = "## B0 Inventory\n- doc: manual-compras \u2014 00_raw/01_business_context/manual-compras.md\n"


class HarvestFunctional(unittest.TestCase):
    def test_doc_inventory_lets_a_fact_cite_a_document(self):
        text = DOC + "## B6 Pantallas\n- [HECHO manual-compras:manual-compras.md] El alta de proveedores tiene cuatro pasos.\n"
        parsed = parse_harvest(text)
        self.assertEqual(parsed["errors"], [])
        self.assertEqual(parsed["docs"], ["manual-compras"])
        self.assertEqual(parsed["repos"], [])
        self.assertEqual(parsed["entries"][0]["block"], "B6")

    def test_unknown_doc_is_an_error(self):
        text = DOC + "## B6 Pantallas\n- [HECHO otro:x.md] Algo.\n"
        parsed = parse_harvest(text)
        self.assertTrue(any("not in the B0 inventory" in e for e in parsed["errors"]))

    def test_b7_b8_are_valid_blocks(self):
        text = (DOC + "## B7 Flujos\n- [HECHO manual-compras:m.md] Flujo de aprobacion.\n"
                "## B8 Reglas y roles\n- [DIVERGENCIA manual-compras:m.md] Dice dos firmas; el codigo una.\n")
        parsed = parse_harvest(text)
        self.assertEqual(parsed["errors"], [])
        self.assertEqual([e["block"] for e in parsed["entries"]], ["B7", "B8"])

    def test_b9_is_still_outside_any_block(self):
        text = DOC + "## B9 Otro\n- [HECHO manual-compras:m.md] Algo.\n"
        parsed = parse_harvest(text)
        self.assertTrue(any("outside any block B0-B8" in e for e in parsed["errors"]))

    def test_repo_only_harvest_unchanged(self):
        text = ("## B0 Inventory\n- repo: api \u2014 svc/api\n## B1 Architecture\n"
                "- [HECHO api:src/app.py] Flask app.\n")
        parsed = parse_harvest(text)
        self.assertEqual(parsed, {
            "repos": ["api"], "docs": [], "errors": [],
            "entries": [{"line": "4", "block": "B1", "kind": "fact", "ref": "api:src/app.py", "text": "Flask app."}],
            "coverage": {"fact": 1, "inferred": 0, "not_found": 0, "out_of_code": 0, "divergence": 0},
        })

    def test_docs_only_inventory_is_enough(self):
        self.assertEqual(parse_harvest(DOC)["errors"], [])

    def test_no_repo_and_no_doc_is_an_error(self):
        self.assertTrue(any("lists no repository" in e for e in parse_harvest("## B0 Inventory\n")["errors"]))

    def test_known_docs_from_an_earlier_harvest_are_accepted(self):
        text = "## B6 Pantallas\n- [HECHO manual-compras:m.md] Algo.\n"
        self.assertEqual(parse_harvest(text, known_docs=("manual-compras",))["errors"], [])

    def test_functional_blocks_have_no_brief_place(self):
        for block in ("B6", "B7", "B8"):
            self.assertNotIn(block, BLOCK_PLACES)

class HarvestFunctionalApply(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        (self.temp / "raw.md").write_text("# Req\n\nObjective: review queues daily.\n", encoding="utf-8")
        self.assertEqual(self.quiet(["init", "FUN", "--brief-version", "1"]), 0)
        self.assertEqual(self.quiet(["ingest", "FUN", "--source", "raw.md"]), 0)
        self.record_path = self.temp / "workspaces" / "FUN" / "01_discovery" / "harvest.json"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    @staticmethod
    def quiet(argv):
        import io
        from contextlib import redirect_stderr, redirect_stdout

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return main(argv)

    def harvest(self, name, text):
        (self.temp / name).write_text(text, encoding="utf-8")
        return self.quiet(["harvest", "FUN", "--source", name])

    def test_docs_accumulate_in_harvest_json(self):
        self.assertEqual(self.harvest("h1.md", DOC + "## B6 Pantallas\n- [HECHO manual-compras:m.md] Cuatro pasos.\n"), 0)
        self.assertEqual(self.harvest("h2.md", "## B7 Flujos\n- [HECHO manual-compras:m.md] Aprobacion.\n"), 0)
        record = json.loads(self.record_path.read_text(encoding="utf-8"))
        self.assertEqual(record["docs"], ["manual-compras"])
        self.assertEqual(sorted({e["block"] for e in record["entries"]}), ["B6", "B7"])

    def test_repo_only_harvest_stores_empty_docs(self):
        text = "## B0\n- repo: api \u2014 svc\n## B1 A\n- [HECHO api:a.py] x.\n"
        self.assertEqual(self.harvest("h.md", text), 0)
        self.assertEqual(json.loads(self.record_path.read_text(encoding="utf-8"))["docs"], [])


if __name__ == "__main__":
    unittest.main()
