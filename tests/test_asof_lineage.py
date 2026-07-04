from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.knowledge.ledger import as_of, current_units, lineage
from sentinel.workspace import workspace_path

# Explicit, well-separated timestamps in the ledger's UTC ISO-8601 shape. utc_now()
# strips microseconds, so real-time events in one second would collide; hand-crafted
# windows keep the as-of test deterministic.
T0 = "2026-01-01T00:00:00+00:00"  # old fact materialized
T1 = "2026-02-01T00:00:00+00:00"  # old fact invalidated / replacement materialized
BEFORE_INVALID = "2026-01-15T00:00:00+00:00"
AFTER_INVALID = "2026-02-15T00:00:00+00:00"


class AsOfUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "ASOF"]), 0)
        self.json_path = workspace_path("ASOF") / "01_discovery" / "knowledge_state.json"
        self.json_path.write_text(
            json.dumps(
                {
                    "units": [
                        {
                            "id": "KLU-NEW",
                            "status": "OPEN",
                            "statement": "New severity matrix",
                            "valid_at": T1,
                            "invalid_at": None,
                            "evidence": {"trace_id": "raw_input", "quote": "new severity matrix"},
                            "links": [{"type": "assumption", "target": "ASM-1"}, {"type": "source", "target": "raw_input"}],
                        }
                    ],
                    "invalidated_units": [
                        {
                            "id": "KLU-OLD",
                            "status": "ASSUMED",
                            "statement": "Old queue risk taxonomy",
                            "valid_at": T0,
                            "invalid_at": T1,
                            "superseded_by": "KLU-NEW",
                            "supersession_reason": "assumption_invalidated",
                            "evidence": {"trace_id": "raw_input", "quote": "current queue risk taxonomy"},
                            "links": [{"type": "assumption", "target": "ASM-1"}, {"type": "gap", "target": "GAP-1"}],
                        }
                    ],
                    "promotion_events": [
                        {"id": "PROMO-001", "origin_ref": "ASM-1", "status": "promoted", "trigger_type": "gap_closed"},
                        {"id": "PROMO-002", "origin_ref": "ASM-1", "status": "revoked", "trigger_type": "gap_closed"},
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_before_invalidation_returns_the_superseded_fact(self):
        ids = {u["id"] for u in as_of("ASOF", BEFORE_INVALID)}
        self.assertEqual(ids, {"KLU-OLD"})

    def test_after_invalidation_returns_the_replacement(self):
        ids = {u["id"] for u in as_of("ASOF", AFTER_INVALID)}
        self.assertEqual(ids, {"KLU-NEW"})

    def test_before_any_fact_returns_nothing(self):
        self.assertEqual(as_of("ASOF", "2025-12-01T00:00:00+00:00"), [])

    def test_empty_timestamp_returns_nothing(self):
        self.assertEqual(as_of("ASOF", ""), [])

    def test_lineage_traces_cited_origin_and_supersession(self):
        chain = lineage("ASOF", "KLU-OLD")
        self.assertEqual(chain["id"], "KLU-OLD")
        self.assertEqual(chain["evidence"]["quote"], "current queue risk taxonomy")
        origin_types = {link["type"] for link in chain["origin"]}
        self.assertEqual(origin_types, {"assumption", "gap"})
        self.assertEqual(chain["superseded_by"], "KLU-NEW")
        self.assertEqual(chain["supersession_reason"], "assumption_invalidated")
        # Promotion lifecycle for the same assumption is surfaced (IMP-154 link).
        self.assertEqual([e["id"] for e in chain["promotion_events"]], ["PROMO-001", "PROMO-002"])

    def test_lineage_unknown_unit_is_empty(self):
        self.assertEqual(lineage("ASOF", "KLU-NOPE"), {})


class AsOfIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        source = self.temp / "input" / "demo.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            "Goal: reduce manual review time for support leads.\n"
            "Users include support leads and operations managers.\n"
            "Scope includes a dashboard for queue triage.\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["init", "AIN"]), 0)
        self.assertEqual(main(["ingest", "AIN", "--source", str(source)]), 0)
        self.payload = json.loads(
            (workspace_path("AIN") / "01_discovery" / "knowledge_state.json").read_text(encoding="utf-8")
        )

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_as_of_now_matches_current_units(self):
        # With no invalidations, as-of at materialization time returns exactly the
        # live projection (derivable, no parallel index).
        materialized_at = self.payload["materialized_at"]
        by_asof = {u["id"] for u in as_of("AIN", materialized_at)}
        by_current = {u["id"] for u in current_units(self.payload["units"])}
        self.assertTrue(by_current)
        self.assertEqual(by_asof, by_current)

    def test_lineage_of_a_real_unit_returns_a_cited_chain(self):
        unit = self.payload["units"][0]
        chain = lineage("AIN", unit["id"])
        self.assertEqual(chain["id"], unit["id"])
        self.assertIn("evidence", chain)
        self.assertIsInstance(chain["origin"], list)
        # At least one materialized unit anchors to a cited origin link.
        self.assertTrue(any(lineage("AIN", u["id"])["origin"] for u in self.payload["units"]))


if __name__ == "__main__":
    unittest.main()
