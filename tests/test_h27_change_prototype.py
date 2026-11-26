"""H27 inc 7a task 4: `/prototype --change CHG --inventory|--manual|--trace` reads only the rows of that change."""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.changes import change_gaps_path, list_changes  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.errors import GateRefusal  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.prototype import PrototypeError, build_inventory, load_inventory  # noqa: E402
from sentinel.prototype_manual import apply_manual  # noqa: E402
from sentinel.prototype_trace import apply_trace  # noqa: E402
from sentinel.sources import load_source_manifest  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "CPRO"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROJECT_PROTOTYPE = FIXTURES / "project_extraction" / "prototipo-alta-proveedor.html"


class ChangePrototypeCase(SyncCase):
    PID = PID

    @classmethod
    def build_workspace(cls) -> None:
        super().build_workspace()
        run_ok(["ingest", PID, "--source", str(cls.FIXTURES / "change_request.md"), "--change"])
        other = sorted(list_changes(PID))[-1]
        run_ok(["sources", PID, "--load", str(PROJECT_PROTOTYPE), "--role", "diseno_nuevo", "--change", other])

    def setUp(self) -> None:
        super().setUp()
        self.other = sorted(list_changes(PID))[-1]
        self.assertNotEqual(self.other, self.CID)

    def write_json(self, name: str, payload: dict) -> Path:
        path = Path.cwd() / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def first_screen(self, change_id: str) -> tuple[str, dict]:
        proto = load_inventory(PID, change_id)["prototypes"][0]
        return proto["source"], proto["screens"][0]

    def stored(self, change_id: str) -> dict:
        path = workspace_path(PID) / "02_requirements" / change_id / "prototype" / "inventory.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_change_inventory_only_its_rows(self) -> None:
        mine = build_inventory(PID, change_id=self.CID)
        theirs = build_inventory(PID, change_id=self.other)
        self.assertEqual(len(mine["prototypes"]), 1)
        self.assertEqual(len(theirs["prototypes"]), 1)
        self.assertTrue(self.stored(self.CID)["prototypes"][0]["path"].endswith("prototipo-aprobaciones.html"))
        self.assertTrue(self.stored(self.other)["prototypes"][0]["path"].endswith("prototipo-alta-proveedor.html"))

    def test_project_inventory_unchanged(self) -> None:
        result = build_inventory(PID)
        self.assertEqual(len(result["prototypes"]), 2)
        base = workspace_path(PID)
        self.assertTrue((base / "02_requirements" / "prototype" / "inventory.json").is_file())
        self.assertFalse((base / "02_requirements" / self.CID / "prototype").exists())

    def test_project_view_of_prototype_works_in_change_only_workspace(self) -> None:
        run_ok(["prototype", PID, "--inventory"])
        run_ok(["view", PID, "--artifact", "prototype"])
        self.assertTrue((workspace_path(PID) / "08_context_packs" / "views" / "prototype.html").is_file()
                        or any((workspace_path(PID) / "08_context_packs" / "views").glob("prototype*.html")))

    def test_change_manual_written(self) -> None:
        build_inventory(PID, change_id=self.CID)
        source, screen = self.first_screen(self.CID)
        element = screen["elements"][0]["id"]
        purpose = "Review the approvals from {{" + element + "}}."
        payload = {"prototype": source, "screens": [{"screen": screen["id"], "purpose": purpose}]}
        result = apply_manual(PID, self.write_json("manual.json", payload), change_id=self.CID)
        self.assertEqual(result["screens_with_manual"], 1)
        view = workspace_path(PID) / "02_requirements" / self.CID / "prototype" / "manual.md"
        self.assertTrue(view.is_file())
        self.assertIn(f"{PID} {self.CID}", view.read_text(encoding="utf-8").splitlines()[0])

    def trace_payload(self, source: str, screen: dict, gap: str) -> dict:
        element = screen["elements"][0]
        return {"prototype": source, "screen": screen["id"], "executed": True, "mode": "existing",
                "elements": [{"element": element["id"], "element_quote": element["text"], "level": "unsupported", "gap": gap}],
                "states": [{"state": s, "status": "shown", "element": element["id"]} for s in ("ideal", "empty", "loading", "error")]}

    def test_change_trace_uses_change_gaps(self) -> None:
        from sentinel.discovery import render_gaps

        build_inventory(PID, change_id=self.CID)
        source, screen = self.first_screen(self.CID)
        base = workspace_path(PID)
        rows = [g for g in parse_gap_rows(change_gaps_path(base, self.CID).read_text(encoding="utf-8")) if g.get("id") != "NONE"]
        project_gap, change_gap = "GAP-ONLY-PROJECT", "GAP-CHG-TRACE"

        def row(gap_id: str) -> dict:
            return {"id": gap_id, "lens": "design", "severity": "medium", "status": "OPEN", "description": "synthetic gap",
                    "question": "Which?", "evidence_mention": "§4.1", "origin": "agent", "resolution_note": ""}

        (base / "01_discovery").mkdir(parents=True, exist_ok=True)
        (base / "01_discovery" / "gaps.md").write_text(render_gaps(PID, [row(project_gap)], "REQ-001", "en"), encoding="utf-8")
        change_gaps_path(base, self.CID).write_text(render_gaps(PID, rows + [row(change_gap)], self.CID, "en"), encoding="utf-8")
        forget_read_snapshots()
        ok = apply_trace(PID, self.write_json("t1.json", self.trace_payload(source, screen, change_gap)), change_id=self.CID)
        self.assertEqual(ok["status"], "traced")
        with self.assertRaises(PrototypeError):
            apply_trace(PID, self.write_json("t2.json", self.trace_payload(source, screen, project_gap)), change_id=self.CID)
        payload = self.trace_payload(source, screen, change_gap)
        payload["executed"] = False
        result = apply_trace(PID, self.write_json("t3.json", payload), change_id=self.CID)
        self.assertEqual(result["verdict"], "not_executed")
        self.assertTrue((base / "02_requirements" / self.CID / "prototype" / "trace").is_dir())

    def test_change_source_must_be_its_row(self) -> None:
        build_inventory(PID, change_id=self.other)
        other_id = self.stored(self.other)["prototypes"][0]["source"]
        with self.assertRaises(PrototypeError):
            build_inventory(PID, other_id, change_id=self.CID)
        with self.assertRaises(GateRefusal):
            build_inventory(PID, change_id="CHG-999")
        self.assertIn(other_id, [r["id"] for r in load_source_manifest(PID)["registry"]])

    def test_no_html_in_change_names_the_load(self) -> None:
        run_ok(["ingest", PID, "--source", str(FIXTURES / "change_borrador.md"), "--change"])
        newest = sorted(list_changes(PID))[-1]
        self.assertNotIn(newest, (self.CID, self.other))
        with self.assertRaises(PrototypeError) as ctx:
            build_inventory(PID, change_id=newest)
        self.assertIn(f"no HTML prototype among the sources of {newest}", str(ctx.exception))
        self.assertIn(f"--role diseno_nuevo --change {newest}", str(ctx.exception))

    def test_cli_change_flag(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(["prototype", PID, "--inventory", "--change", self.CID])
        self.assertEqual(code, 0, out.getvalue())
        self.assertEqual(len(json.loads(out.getvalue())["prototypes"]), 1)
