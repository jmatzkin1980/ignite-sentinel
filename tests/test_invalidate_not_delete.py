from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.assumptions import apply_assumptions
from sentinel.cli import main
from sentinel.core.io import read_json
from sentinel.discovery import parse_gap_rows
from sentinel.knowledge.ledger import (
    assumption_link_target,
    materialize_knowledge_ledger,
    record_superseded_units,
)
from sentinel.sync import sync_change
from sentinel.workspace import workspace_path


class SupersessionUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "SUP"]), 0)
        self.json_path = workspace_path("SUP") / "01_discovery" / "knowledge_state.json"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_assumption_link_target_extracts_id(self):
        unit = {"id": "KLU-001", "links": [{"type": "gap", "target": "GAP-1"}, {"type": "assumption", "target": "ASM-9"}]}
        self.assertEqual(assumption_link_target(unit), "ASM-9")
        self.assertIsNone(assumption_link_target({"id": "KLU-2", "links": []}))

    def test_records_superseded_with_typed_edge_and_never_deletes(self):
        self.json_path.write_text(json.dumps({"units": [], "invalidated_units": []}), encoding="utf-8")
        before = [{"id": "KLU-001", "status": "ASSUMED", "statement": "X", "invalid_at": None,
                   "links": [{"type": "assumption", "target": "ASM-1"}]}]
        after = [{"id": "KLU-007", "status": "OPEN", "statement": "X",
                  "links": [{"type": "assumption", "target": "ASM-1"}]}]
        entries = record_superseded_units("SUP", before, after, {"ASM-1"})
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["superseded_by"], "KLU-007")
        self.assertEqual(entries[0]["supersession_reason"], "assumption_invalidated")
        self.assertIsNotNone(entries[0]["invalid_at"])
        # Persisted append-only; the old ASSUMED version is kept, not deleted.
        history = read_json(self.json_path, {})["invalidated_units"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "ASSUMED")

    def test_non_invalidated_assumptions_are_untouched(self):
        self.json_path.write_text(json.dumps({"units": [], "invalidated_units": []}), encoding="utf-8")
        before = [{"id": "KLU-001", "invalid_at": None, "links": [{"type": "assumption", "target": "ASM-2"}]}]
        self.assertEqual(record_superseded_units("SUP", before, [], {"ASM-1"}), [])

    def test_materialize_carries_forward_history(self):
        self.json_path.write_text(
            json.dumps({"units": [], "invalidated_units": [{"id": "KLU-OLD", "invalid_at": "t0"}]}),
            encoding="utf-8",
        )
        materialize_knowledge_ledger("SUP", "", [], "", {})
        payload = read_json(self.json_path, {})
        self.assertEqual([u["id"] for u in payload["invalidated_units"]], ["KLU-OLD"])


RAW = (
    "Ops leads triage a risk queue. The current queue risk taxonomy is used during manual triage.\n"
    "Acceptance: leads see stale queue risk before standup.\n"
)


class InvalidateNotDeleteIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "risk.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "IND"]), 0)
        self.assertEqual(main(["ingest", "IND", "--source", str(raw)]), 0)
        self.ws = workspace_path("IND")
        gaps = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        gap_id = next(g["id"] for g in gaps if g.get("id") != "NONE")
        src = self.temp / "asm.json"
        src.write_text(json.dumps({"assumptions": [{
            "id": "ASM-RISK-TAXONOMY", "lens": "product",
            "statement": "The board can provisionally use the current queue risk taxonomy.",
            "owner": "Product Lead", "risk": "med",
            "justification": "The current queue risk taxonomy is used during manual triage.",
            "closes_gap": gap_id,
        }]}), encoding="utf-8")
        apply_assumptions("IND", src)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_invalidating_sync_preserves_the_prior_unit_with_supersession(self):
        change = self.temp / "change.md"
        change.write_text(
            "ASM-RISK-TAXONOMY is no longer valid; the queue risk taxonomy was replaced by a new severity matrix.",
            encoding="utf-8",
        )
        result = sync_change("IND", change, "taxonomy replaced")
        metabolism = result["knowledge_metabolism"]
        self.assertIn("ASM-RISK-TAXONOMY", metabolism["invalidated_assumptions"])
        # The prior ASSUMED unit is preserved in append-only history, not deleted.
        payload = read_json(self.ws / "01_discovery" / "knowledge_state.json", {})
        history = payload.get("invalidated_units", [])
        self.assertTrue(history)
        entry = history[-1]
        self.assertEqual(entry["supersession_reason"], "assumption_invalidated")
        self.assertIsNotNone(entry["invalid_at"])
        self.assertEqual(assumption_link_target(entry), "ASM-RISK-TAXONOMY")
        # The live ledger no longer carries it as ASSUMED (it is OPEN now).
        live = [u for u in payload["units"] if assumption_link_target(u) == "ASM-RISK-TAXONOMY"]
        self.assertTrue(all(u["status"] != "ASSUMED" for u in live))


if __name__ == "__main__":
    unittest.main()
