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
    UnknownPromotionTrigger,
    active_promotions,
    materialize_knowledge_ledger,
    promotion_events,
    record_promotion_event,
)
from sentinel.knowledge.metabolism import metabolize_knowledge
from sentinel.workspace import workspace_path


class PromotionEventUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "PROMO"]), 0)
        self.json_path = workspace_path("PROMO") / "01_discovery" / "knowledge_state.json"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_records_typed_event_with_citable_origin(self):
        self.json_path.write_text(json.dumps({"units": [], "promotion_events": []}), encoding="utf-8")
        event = record_promotion_event(
            "PROMO", trigger_type="gap_closed", origin_ref="ASM-1", statement="evidence quote"
        )
        self.assertIsNotNone(event)
        self.assertEqual(event["node_type"], "promotion_event")
        self.assertEqual(event["trigger_type"], "gap_closed")
        self.assertEqual(event["origin_ref"], "ASM-1")
        self.assertEqual(event["status"], "promoted")
        self.assertTrue(event["id"].startswith("PROMO-"))
        self.assertTrue(event["timestamp"])
        # Persisted append-only.
        self.assertEqual(len(read_json(self.json_path, {})["promotion_events"]), 1)

    def test_unknown_trigger_type_fails_visibly(self):
        self.json_path.write_text(json.dumps({"units": [], "promotion_events": []}), encoding="utf-8")
        with self.assertRaises(UnknownPromotionTrigger):
            record_promotion_event("PROMO", trigger_type="vibes", origin_ref="ASM-1")

    def test_novelty_gate_does_not_re_fire_known_content(self):
        self.json_path.write_text(json.dumps({"units": [], "promotion_events": []}), encoding="utf-8")
        first = record_promotion_event("PROMO", trigger_type="gap_closed", origin_ref="ASM-1")
        second = record_promotion_event("PROMO", trigger_type="human_decision", origin_ref="ASM-1")
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(promotion_events("PROMO")), 1)

    def test_revocation_appends_event_and_leaves_original_intact(self):
        self.json_path.write_text(json.dumps({"units": [], "promotion_events": []}), encoding="utf-8")
        promoted = record_promotion_event("PROMO", trigger_type="gap_closed", origin_ref="ASM-1")
        revoked = record_promotion_event("PROMO", trigger_type="gap_closed", origin_ref="ASM-1", status="revoked")
        self.assertIsNotNone(revoked)
        self.assertEqual(revoked["status"], "revoked")
        events = promotion_events("PROMO")
        self.assertEqual([e["status"] for e in events], ["promoted", "revoked"])
        # Original promoted event is preserved, not overwritten.
        self.assertEqual(events[0]["id"], promoted["id"])
        # Revocation removes it from the active set; a fresh promotion is novel again.
        self.assertNotIn("ASM-1", active_promotions(events))
        reprom = record_promotion_event("PROMO", trigger_type="gap_closed", origin_ref="ASM-1")
        self.assertIsNotNone(reprom)

    def test_revocation_without_prior_promotion_is_a_no_op(self):
        self.json_path.write_text(json.dumps({"units": [], "promotion_events": []}), encoding="utf-8")
        self.assertIsNone(
            record_promotion_event("PROMO", trigger_type="gap_closed", origin_ref="ASM-9", status="revoked")
        )
        self.assertEqual(promotion_events("PROMO"), [])

    def test_materialize_carries_forward_promotion_events(self):
        self.json_path.write_text(
            json.dumps({"units": [], "promotion_events": [{"id": "PROMO-001", "origin_ref": "ASM-1", "status": "promoted"}]}),
            encoding="utf-8",
        )
        materialize_knowledge_ledger("PROMO", "", [], "", {})
        payload = read_json(self.json_path, {})
        self.assertEqual([e["id"] for e in payload["promotion_events"]], ["PROMO-001"])


RAW = (
    "Ops leads triage a risk queue. The current queue risk taxonomy is used during manual triage.\n"
    "Acceptance: leads see stale queue risk before standup.\n"
)


class PromotionEventIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "risk.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "PIN"]), 0)
        self.assertEqual(main(["ingest", "PIN", "--source", str(raw)]), 0)
        self.ws = workspace_path("PIN")
        gaps = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        self.gap_id = next(g["id"] for g in gaps if g.get("id") != "NONE")
        src = self.temp / "asm.json"
        src.write_text(json.dumps({"assumptions": [{
            "id": "ASM-RISK-TAXONOMY", "lens": "product",
            "statement": "The board can provisionally use the current queue risk taxonomy.",
            "owner": "Product Lead", "risk": "med",
            "justification": "The current queue risk taxonomy is used during manual triage.",
            "closes_gap": self.gap_id,
        }]}), encoding="utf-8")
        apply_assumptions("PIN", src)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_validated_assumption_promotes_then_gate_and_revocation(self):
        # A closed gap validates the assumption -> promotion event (gap_closed).
        result = metabolize_knowledge("PIN", "gap closed", validated_gap_ids={self.gap_id})
        promoted = result["promotion_events"]
        self.assertEqual(len(promoted), 1)
        self.assertEqual(promoted[0]["trigger_type"], "gap_closed")
        self.assertEqual(promoted[0]["origin_ref"], "ASM-RISK-TAXONOMY")
        self.assertEqual(promoted[0]["status"], "promoted")

        # Re-running the same governed signal does not re-fire (novelty gate).
        again = metabolize_knowledge("PIN", "gap closed again", validated_gap_ids={self.gap_id})
        self.assertEqual(again["promotion_events"], [])

        # Invalidating the assumption revokes its promotion; the history is append-only.
        change = self.temp / "change.md"
        change.write_text(
            "ASM-RISK-TAXONOMY is no longer valid; the queue risk taxonomy was replaced by a new severity matrix.",
            encoding="utf-8",
        )
        from sentinel.sync import sync_change

        sync_change("PIN", change, "taxonomy replaced")
        events = promotion_events("PIN")
        statuses = [e["status"] for e in events if e["origin_ref"] == "ASM-RISK-TAXONOMY"]
        self.assertEqual(statuses, ["promoted", "revoked"])
        self.assertNotIn("ASM-RISK-TAXONOMY", active_promotions(events))


if __name__ == "__main__":
    unittest.main()
