"""H27 inc 6a task 2: what a new source of a change touches: carried claims, claims and elements to re-read."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.change_sync import apply_touched_set, element_delta  # noqa: E402
from sentinel.changes import list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots, read_json, write_json  # noqa: E402
from sentinel.crosses import cross_path  # noqa: E402
from sentinel.crosses.state import cross_status  # noqa: E402
from sentinel.extraction import extraction_dir  # noqa: E402
from sentinel.extraction.inventory import inventory_path, inventory_state  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PID = "TCHS"
CID = "CHG-001"


class TouchedCase(SyncCase):
    PID = PID

    def load_v2(self, source: Path | None = None) -> str:
        """Load the request v2 and confirm it replaces the first one; returns its id."""
        if source is None:
            Path("v2").mkdir(exist_ok=True)
            source = self.write_v2("v2/pedido.md")
        old = self.ids()["pedido"]
        new = json.loads(run_ok(["sources", PID, "--load", str(source), "--role", "pedido", "--change", CID]))["source_id"]
        run_ok(["sources", PID, "--id", old, "--superseded-by", new, "--reason", "version nueva"])
        forget_read_snapshots()
        return new

    def apply(self, old: str | None, new: str, **kwargs) -> dict:
        forget_read_snapshots()
        return apply_touched_set(PID, CID, previous_id=old, new_id=new, **kwargs)

    def record(self, kind: str) -> dict:
        return read_json(cross_path(workspace_path(PID), CID, kind), {})

    def set_language(self, language: str) -> None:
        changes = {key: dict(value) for key, value in list_changes(PID).items()}
        changes[CID]["language"] = language
        update_state(PID, changes=changes)
        forget_read_snapshots()


class ChangedQuote(TouchedCase):
    def test_changed_quote_is_touched_not_carried(self):
        old = self.ids()["pedido"]
        new = self.load_v2()
        result = self.apply(old, new)
        self.assertEqual(result["crosses"]["diseno"]["touched"], [5])
        self.assertEqual(result["crosses"]["diseno"]["carried"], [1, 2, 3])
        claims = {c["n"]: c for c in self.record("diseno")["claims"]}
        self.assertEqual({c["source_id"] for c in claims[5]["citations"] if c["side"] == "pedido"}, {old})
        self.assertEqual({c["source_id"] for c in claims[1]["citations"] if c["side"] == "pedido"}, {new})

    def test_carried_claims_keep_gap_and_answer(self):
        old = self.ids()["pedido"]
        gap = next(g["id"] for g in self._gap_rows() if g["id"].startswith("GAP-CON-"))
        before = next(g for g in self._gap_rows() if g["id"] == gap)
        self.assertEqual(str(before.get("closure_reason")).strip("`"), "answered")
        new = self.load_v2()
        result = self.apply(old, new)
        self.assertEqual(result["crosses"]["contradicciones"]["carried"], [1])
        claim = self.record("contradicciones")["claims"][0]
        self.assertEqual({c["source_id"] for c in claim["citations"]}, {new})
        self.assertTrue(all(c["line"] for c in claim["citations"]))
        self.assertEqual(claim["gap"], gap)
        self.assertIn(gap, self.record("contradicciones")["gaps"])
        self.assertNotIn(gap, self.open_gaps())
        self.assertEqual(next(g for g in self._gap_rows() if g["id"] == gap), before)

    def test_changed_element_listed(self):
        old = self.ids()["pedido"]
        new = self.load_v2()
        result = self.apply(old, new)
        self.assertEqual(result["extraction"]["changed"], ["RN-02"])
        self.assertEqual(result["extraction"]["new"], [])
        self.assertEqual(result["extraction"]["removed"], [])
        self.assertEqual(result["extraction"]["inventory"], "absent")
        self.assertFalse(inventory_path(workspace_path(PID), CID).exists())
        self.assertEqual(result["role"], "pedido")
        self.assertEqual((result["source_id"], result["previous_id"]), (new, old))

    def test_pending_delta_marks_kind_stale(self):
        old = self.ids()["pedido"]
        new = self.load_v2()
        result = self.apply(old, new)
        kinds = cross_status(PID, CID)["kinds"]
        self.assertEqual(kinds["diseno"]["state"], "stale")
        self.assertEqual(kinds["diseno"]["delta"]["touched"], [5])
        self.assertEqual(kinds["diseno"]["delta"]["elements"], result["extraction"]["changed"])
        self.assertEqual(kinds["contradicciones"]["state"], "stale")
        self.assertEqual(kinds["contradicciones"]["delta"]["touched"], [])
        self.assertEqual(kinds["linea_de_base"]["state"], "done")
        self.assertNotIn("delta", kinds["linea_de_base"])
        delta = self.record("diseno")["pending_delta"]
        self.assertEqual((delta["source_id"], delta["design"]), (new, None))
        self.assertEqual(delta["removed"], [])
        # the basis follows the rebased claims
        self.assertEqual(self.record("diseno")["basis"]["pedido"], [new])

    def test_kind_without_delta_has_no_key(self):
        status = cross_status(PID, CID)["kinds"]
        for kind in ("diseno", "contradicciones"):
            self.assertNotIn("delta", status[kind])
            self.assertEqual(status[kind]["state"], "done")

    def test_commands_per_kind(self):
        old = self.ids()["pedido"]
        result = self.apply(old, self.load_v2())
        cmd = f"/cross {PID} --change {CID} --kind diseno --claims ARCHIVO --delta"
        self.assertEqual(result["crosses"]["diseno"]["command"], cmd)
        self.assertTrue(result["crosses"]["diseno"]["delta"])
        self.assertIn(cmd, result["commands"])
        self.assertEqual(result["baseline"], {"stale": False, "command": None})

    def test_second_run_keeps_the_first_touched_claims(self):
        old = self.ids()["pedido"]
        new = self.load_v2()
        self.apply(old, new)
        again = self.apply(None, new)
        self.assertEqual(self.record("diseno")["pending_delta"]["touched"], [5])
        self.assertEqual(again["crosses"]["diseno"]["touched"], [5])


class HeaderOnly(TouchedCase):
    def test_header_only_version_carries_everything(self):
        old = self.ids()["pedido"]
        new = self.load_v2(FIXTURES / "change_crosses" / "pedido_v2.md")
        result = self.apply(old, new)
        for kind in ("diseno", "contradicciones"):
            self.assertEqual(result["crosses"][kind]["touched"], [])
            self.assertFalse(result["crosses"][kind]["delta"])
            self.assertIsNone(result["crosses"][kind]["command"])
            self.assertNotIn("pending_delta", self.record(kind))
        # the quote of claim 5 is still in the request: with only headings changed it is carried too
        self.assertEqual(result["crosses"]["diseno"]["carried"], [1, 2, 3, 5])
        self.assertEqual(result["extraction"]["changed"], [])
        self.assertIn("SEC-proceso-to-be", result["extraction"]["new"])
        self.assertIn("SEC-proceso", result["extraction"]["removed"])
        self.assertEqual(result["commands"], [])
        kinds = cross_status(PID, CID)["kinds"]
        for kind in ("diseno", "contradicciones"):
            self.assertEqual(kinds[kind]["state"], "done")
            self.assertEqual(kinds[kind]["new_sources"], [])
            self.assertEqual(kinds[kind]["stale_sources"], [])


class NewDesign(TouchedCase):
    def test_new_design_source_needs_design_delta(self):
        second = Path.cwd() / "prototipo-reportes.html"
        html = (FIXTURES / "change_crosses" / "prototipo-aprobaciones.html").read_text(encoding="utf-8")
        second.write_text(html.replace("</body>", "<p>Pantalla de reportes de altas</p>\n</body>"), encoding="utf-8")
        new = json.loads(run_ok(["sources", PID, "--load", str(second), "--role", "diseno_nuevo", "--change", CID]))["source_id"]
        result = self.apply(None, new)
        self.assertEqual(result["role"], "diseno_nuevo")
        self.assertTrue(result["crosses"]["diseno"]["delta"])
        self.assertNotIn("contradicciones", result["crosses"])
        self.assertEqual(self.record("diseno")["pending_delta"]["design"], new)
        self.assertEqual(cross_status(PID, CID)["kinds"]["diseno"]["state"], "stale")
        self.assertEqual(cross_status(PID, CID)["kinds"]["contradicciones"]["state"], "done")

    def test_design_version_always_asks_for_the_delta(self):
        old = self.ids()["diseno"]
        second = Path.cwd() / "prototipo-v2.html"
        html = (FIXTURES / "change_crosses" / "prototipo-aprobaciones.html").read_text(encoding="utf-8")
        second.write_text(html.replace("</body>", "<p>Pantalla nueva de reportes de altas</p>\n</body>"), encoding="utf-8")
        new = json.loads(run_ok(["sources", PID, "--load", str(second), "--role", "diseno_nuevo", "--change", CID]))["source_id"]
        run_ok(["sources", PID, "--id", old, "--superseded-by", new, "--reason", "version nueva"])
        forget_read_snapshots()
        delta = self.record("diseno")["pending_delta"]
        self.assertEqual(delta["design"], new)
        self.assertEqual(delta["touched"], [])
        status = cross_status(PID, CID)["kinds"]["diseno"]
        self.assertEqual(status["state"], "stale")
        result = self.apply(old, new)
        self.assertTrue(result["crosses"]["diseno"]["delta"])
        self.assertEqual(result["crosses"]["diseno"]["touched"], [])
        self.assertEqual(self.record("diseno")["pending_delta"]["design"], new)

    def test_plan_previo_touches_nothing(self):
        plan = Path.cwd() / "plan.md"
        plan.write_text("# Plan previo\n\nEl plan de la etapa anterior no cambia el alcance de este alta.\n", encoding="utf-8")
        new = json.loads(run_ok(["sources", PID, "--load", str(plan), "--role", "plan_previo", "--change", CID]))["source_id"]
        result = self.apply(None, new)
        self.assertEqual(result["crosses"], {})
        self.assertEqual(result["commands"], [])
        self.assertTrue(Path(result["report_path"]).is_file())


class Report(TouchedCase):
    def test_sync_report_in_change_language(self):
        old = self.ids()["pedido"]
        result = self.apply(old, self.load_v2(), note="llegó el pedido v2")
        text = Path(result["report_path"]).read_text(encoding="utf-8")
        self.assertEqual(Path(result["report_path"]), workspace_path(PID) / "01_discovery" / CID / "sync_report.md")
        self.assertTrue(text.startswith(f"# Sync del cambio {CID}"))
        self.assertIn("llegó el pedido v2", text)
        for heading in ("## Afirmaciones que siguen vigentes", "## Afirmaciones a releer",
                        "## Elementos nuevos, cambiados o quitados", "## Próximos comandos"):
            self.assertIn(heading, text)
        reread = text.split("## Afirmaciones a releer")[1].split("## ")[0]
        self.assertIn("5", reread)
        commands = text.split("## Próximos comandos")[1]
        self.assertIn("--kind diseno --claims ARCHIVO --delta", commands)
        self.assertIn("RN-02", text.split("## Elementos nuevos, cambiados o quitados")[1])

    def test_sync_report_in_english(self):
        self.set_language("en")
        old = self.ids()["pedido"]
        result = self.apply(old, self.load_v2())
        text = Path(result["report_path"]).read_text(encoding="utf-8")
        self.assertTrue(text.startswith(f"# Change sync {CID}"))
        for heading in ("## Claims carried", "## Claims to re-read", "## New, changed or removed elements", "## Next commands"):
            self.assertIn(heading, text)
        self.assertIn("--kind diseno --claims FILE --delta", text)
        self.assertNotIn("ARCHIVO", text)

    def test_empty_sections_say_nothing_new(self):
        old = self.ids()["pedido"]
        new = self.load_v2(FIXTURES / "change_crosses" / "pedido_v2.md")
        text = Path(self.apply(old, new)["report_path"]).read_text(encoding="utf-8")
        self.assertIn("_sin novedad_", text.split("## Afirmaciones a releer")[1].split("## ")[0])
        self.assertIn("_sin novedad_", text.split("## Próximos comandos")[1])


class Inventory(TouchedCase):
    def test_existing_inventory_is_rebuilt(self):
        run_ok(["extract", PID, "--change", CID])
        path = inventory_path(workspace_path(PID), CID)
        inventory = read_json(path, {})
        sha = next(e["sha"] for e in inventory["elements"] if e["id"] == "RN-02")
        write_json(extraction_dir(workspace_path(PID), CID) / "proposals.json",
                   {"items": {"RN-02": {"element_sha": sha, "status": "confirmed"}}})
        old = self.ids()["pedido"]
        new = self.load_v2()
        result = self.apply(old, new)
        self.assertEqual(result["extraction"]["inventory"], "rebuilt")
        self.assertEqual(inventory_state(PID, CID), "current")
        self.assertIn("RN-02", result["extraction"]["stale_proposals"])


class Delta(TouchedCase):
    def test_first_version_is_all_new(self):
        delta = element_delta(PID, CID, None, self.ids()["pedido"])
        self.assertIn("RN-02", delta["new"])
        self.assertEqual((delta["changed"], delta["removed"]), ([], []))


if __name__ == "__main__":
    unittest.main()
