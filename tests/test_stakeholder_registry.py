"""IMP-192: governed stakeholder registry + elicitation routing."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import parse_gap_rows, render_interview_script
from sentinel.stakeholders import (
    add_stakeholder,
    load_stakeholders,
    owner_for_lens,
    parse_stakeholders,
    render_stakeholders,
)


def _gap(**over):
    base = {"id": "GAP-A", "lens": "product", "severity": "critical", "status": "OPEN"}
    base.update(over)
    return base


class RegistryUnitTests(unittest.TestCase):
    def test_render_parse_round_trip(self):
        rows = [
            {"id": "STK-001", "name": "Ops Lead", "domain": "product", "topic": "queue risk", "respondent_profile": "business", "notes": "n1"},
        ]
        text = render_stakeholders("X", rows, "en")
        parsed = parse_stakeholders(text)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["id"], "STK-001")
        self.assertEqual(parsed[0]["domain"], "product")
        self.assertEqual(parsed[0]["respondent_profile"], "business")

    def test_empty_registry_has_explicit_marker(self):
        text = render_stakeholders("X", [], "en")
        self.assertIn("No stakeholders registered", text)
        self.assertEqual(parse_stakeholders(text), [])

    def test_owner_for_lens_is_deterministic_and_never_fabricated(self):
        stk = [
            {"id": "STK-002", "name": "B", "domain": "product", "respondent_profile": "", "topic": "", "notes": ""},
            {"id": "STK-001", "name": "A", "domain": "product", "respondent_profile": "", "topic": "", "notes": ""},
        ]
        # Stable by id when several own the same domain.
        self.assertEqual(owner_for_lens("product", stk)["id"], "STK-001")
        # No match -> None, never an invented owner.
        self.assertIsNone(owner_for_lens("quality", stk))
        self.assertIsNone(owner_for_lens("", stk))


class RegistryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(
            "# Risk Dashboard\n\nOperations leads need a dashboard for queue risk before standup.",
            encoding="utf-8",
        )
        self.assertEqual(main(["init", "STK"]), 0)
        self.assertEqual(main(["ingest", "STK", "--source", str(self.raw)]), 0)
        self.ws = self.temp / "workspaces" / "STK"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_registry_is_not_created_until_the_cli_writes_it(self):
        # Discovery alone does not create the registry (mutable only via /stakeholders).
        self.assertFalse((self.ws / "01_discovery" / "stakeholders.md").exists())
        self.assertEqual(load_stakeholders("STK"), [])

    def test_add_via_cli_auto_ids_and_persists(self):
        self.assertEqual(main(["stakeholders", "STK", "--add", "--name", "Ops Lead", "--domain", "product", "--profile", "business"]), 0)
        rows = load_stakeholders("STK")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "STK-001")
        self.assertEqual(rows[0]["domain"], "product")
        self.assertEqual(rows[0]["respondent_profile"], "business")
        self.assertTrue((self.ws / "01_discovery" / "stakeholders.md").exists())

    def test_duplicate_id_is_rejected(self):
        add_stakeholder("STK", name="A", domain="product", stakeholder_id="STK-001")
        with self.assertRaises(RuntimeError):
            add_stakeholder("STK", name="B", domain="quality", stakeholder_id="STK-001")

    def test_unrecognized_profile_is_dropped_not_invented(self):
        result = add_stakeholder("STK", name="A", domain="product", profile="wizard")
        self.assertEqual(result["added"]["respondent_profile"], "")
        self.assertTrue(result["profile_ignored"])

    def test_missing_name_or_domain_errors(self):
        with self.assertRaises(RuntimeError):
            add_stakeholder("STK", name="", domain="product")
        with self.assertRaises(RuntimeError):
            add_stakeholder("STK", name="A", domain="")


class RoutingTests(unittest.TestCase):
    def test_interview_groups_by_owner_with_explicit_unassigned(self):
        gaps = [
            _gap(id="GAP-A", lens="product", severity="critical"),
            _gap(id="GAP-B", lens="quality", severity="critical"),
        ]
        stk = [{"id": "STK-001", "name": "Ops", "domain": "product", "respondent_profile": "business", "topic": "", "notes": ""}]
        script = render_interview_script("D", gaps, "en", stk)
        self.assertIn("Owner: Ops (domain `product`", script)
        self.assertIn("respondent_profile `business`", script)
        self.assertIn("Unassigned (no stakeholder owner", script)
        # GAP-A routed under its owner; GAP-B (no owner) under the unassigned bucket.
        self.assertLess(script.index("Owner: Ops"), script.index("GAP-A"))
        self.assertLess(script.index("Unassigned"), script.index("GAP-B"))

    def test_no_registry_keeps_lens_grouping_backward_compatible(self):
        gaps = [_gap(id="GAP-A", lens="product", severity="critical")]
        script = render_interview_script("D", gaps, "en")  # stakeholders=None
        self.assertNotIn("Owner:", script)
        self.assertNotIn("Unassigned", script)
        self.assertIn("### product", script)


if __name__ == "__main__":
    unittest.main()
