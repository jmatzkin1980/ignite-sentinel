"""IMP-406 (H27 inc 1) task 5: the reading plan, in batches the agent reads in full."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, run_ok, waive_crosses  # noqa: E402

from sentinel.core.io import forget_read_snapshots, read_json  # noqa: E402
from sentinel.extraction import extraction_dir  # noqa: E402
from sentinel.extraction.inventory import build_inventory, element_lines, element_text, load_inventory  # noqa: E402
from sentinel.extraction.proposals import record_proposals  # noqa: E402
from sentinel.extraction.reading_plan import plan_batches, reading_plan_status  # noqa: E402
from sentinel.readiness_verdict import change_next_step  # noqa: E402
from sentinel.status import change_status  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LARGO = FIXTURES / "change_extraction" / "pedido_largo.md"
PID = "FIN"
CID = "CHG-001"


def element(name: str, chars: int, source: str = "F-01", lines: tuple[int, int] = (1, 1)) -> dict:
    return {"id": name, "chars": chars, "source_id": source, "path": f"{source}.md", "lines": list(lines)}


class Batching(unittest.TestCase):
    def test_plan_batches(self):
        sizes = [30, 40, 50, 100, 10]
        found = plan_batches([element(f"e{i}", c) for i, c in enumerate(sizes, 1)], budget=100)
        self.assertEqual([b["elements"] for b in found], [["e1", "e2"], ["e3"], ["e4"], ["e5"]])
        self.assertEqual([b["number"] for b in found], [1, 2, 3, 4])
        self.assertEqual(found[0]["chars"], 70)
        found = plan_batches([element("a", 10), element("b", 250), element("c", 10)], budget=100)
        self.assertEqual([b["elements"] for b in found], [["a"], ["b"], ["c"]])

    def test_ranges_by_source(self):
        found = plan_batches([
            element("a", 10, "F-01", (3, 5)), element("b", 10, "F-02", (1, 4)), element("c", 10, "F-01", (6, 9)),
        ], budget=100)
        self.assertEqual(len(found), 1)
        self.assertEqual(
            [(r["source_id"], r["lines"]) for r in found[0]["ranges"]], [("F-01", [3, 9]), ("F-02", [1, 4])])


class Plan(SnapshotWorkspaceCase):
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
        waive_crosses(PID, CID)

    def setUp(self):
        super().setUp()
        forget_read_snapshots()  # the work folder keeps its path between tests; what an earlier test read is gone

    def propose(self, ids: list[str]) -> None:
        """Propose each element as a section, with the whole element as its Líneas."""
        forget_read_snapshots()
        base = workspace_path(PID)
        by_id = {e["id"]: e for e in load_inventory(base, CID)["elements"]}
        blocks = []
        for element_id in ids:
            item = by_id[element_id]
            quote = " ".join((element_text(base, item) or "").split())[:60].strip()
            first, last = element_lines(item)
            blocks.append("\n".join([
                f"### {element_id}", "- Tratamiento: seccion", f"- Líneas: {first}-{last}", "- Seccion: reglas",
                f'- Cita: "{quote}"', "",
            ]))
        path = Path.cwd() / "plan_proposals.md"
        path.write_text("\n".join(blocks), encoding="utf-8")
        result = record_proposals(PID, CID, path)
        self.assertEqual(result["rejected"], {}, result)

    def test_inventory_writes_the_plan(self):
        out = json.loads(run_ok(["extract", PID, "--change", CID]))
        self.assertIn("plan de lectura: 1 lote(s)", out["message"])
        folder = extraction_dir(workspace_path(PID), CID)
        forget_read_snapshots()
        plan = read_json(folder / "reading_plan.json", None)
        inventory = load_inventory(workspace_path(PID), CID)
        self.assertEqual(plan["budget_chars"], 60000)
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["inventory_version"], inventory["version"])
        self.assertEqual(len(plan["batches"]), 1)
        self.assertEqual(plan["batches"][0]["elements"], [e["id"] for e in inventory["elements"]])
        self.assertEqual(plan["batches"][0]["ranges"][0]["lines"], [4, 98])
        self.assertIn("Lote 1 de 1", (folder / "reading_plan.md").read_text(encoding="utf-8"))

    def test_plan_is_rewritten_when_missing(self):
        build_inventory(PID, CID)
        folder = extraction_dir(workspace_path(PID), CID)
        (folder / "reading_plan.json").unlink()
        (folder / "reading_plan.md").unlink()
        forget_read_snapshots()
        build_inventory(PID, CID)
        self.assertTrue((folder / "reading_plan.json").exists())
        self.assertTrue((folder / "reading_plan.md").exists())

    def test_next_and_status_name_the_batch(self):
        with patch("sentinel.extraction.reading_plan.READING_BUDGET", 2000):
            build_inventory(PID, CID)
            forget_read_snapshots()
            batches = plan_batches(load_inventory(workspace_path(PID), CID)["elements"])
            self.assertGreater(len(batches), 2)
            step = change_next_step(PID, CID)
            self.assertEqual(step["key"], "extract_proposals")
            self.assertIn("lote 1 de ", step["text"])
            self.assertIn(f"{batches[0]['elements'][0]} … {batches[0]['elements'][-1]}", step["text"])
            self.assertIn("reading_plan.md", step["text"])
            self.assertEqual(change_status(PID, CID)["reading_plan"]["text"], f"lote 1 de {len(batches)}")
            self.propose(batches[0]["elements"])
            step = change_next_step(PID, CID)
            self.assertEqual(step["key"], "extract_proposals")
            self.assertIn("lote 2 de ", step["text"])
            status = change_status(PID, CID)["reading_plan"]
            self.assertEqual((status["text"], status["next"], status["proposed"]), (f"lote 2 de {len(batches)}", 2, 1))
            for batch in batches[1:]:
                self.propose(batch["elements"])
            self.assertNotEqual(change_next_step(PID, CID)["key"], "extract_proposals")
            status = reading_plan_status(PID, CID)
            self.assertEqual(status["text"], f"{len(batches)} de {len(batches)} lotes propuestos")
            self.assertIsNone(status["next_batch"])

    def test_status_without_inventory(self):
        status = reading_plan_status(PID, CID)
        self.assertEqual((status["text"], status["total"], status["next"]), ("sin plan", 0, None))


if __name__ == "__main__":
    unittest.main()
