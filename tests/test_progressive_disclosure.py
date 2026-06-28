"""IMP-127 — Cross-cutting progressive disclosure + portable needs-context gate.

Three runtime capabilities, all degradation-safe and LanceDB-agnostic:
- a global character budget + cross-section chunk dedup over a multi-section pack
  (apply_pack_disclosure_budget);
- focused, pointer-only context packs for high-volume flows (build_focus_pack),
  wired into /sync and discovery;
- a soft "needs-context" gate (evaluate_needs_context) surfaced in /health,
  strict opt-in, triggered by indexed volume rather than by LanceDB.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sentinel.cli import main
from sentinel.health import run_health
from sentinel.memory import ContextBroker, apply_pack_disclosure_budget
from sentinel.protocols import evaluate_needs_context

ROOT = Path(__file__).parent
FIXTURE = ROOT / "fixtures" / "evals" / "support-dashboard" / "requirement.md"


class DisclosureBudgetTests(unittest.TestCase):
    def test_dedup_drops_later_repeat(self) -> None:
        sections = {
            "a": {"results": [{"chunk_id": "c1", "summary": "x"}, {"chunk_id": "c2", "summary": "y"}]},
            "b": {"results": [{"chunk_id": "c3", "summary": "z"}, {"chunk_id": "c1", "summary": "x"}]},
        }
        budget = apply_pack_disclosure_budget(sections, global_budget_chars=0)
        self.assertEqual([r["chunk_id"] for r in sections["a"]["results"]], ["c1", "c2"])
        # b keeps its fresh first hit and drops the repeat of c1 already shown in a.
        self.assertEqual([r["chunk_id"] for r in sections["b"]["results"]], ["c3"])
        self.assertEqual(sections["b"]["disclosure_deduped"], 1)
        self.assertEqual(budget["deduped_chunks"], 1)
        self.assertEqual(budget["truncated_chunks"], 0)

    def test_global_budget_truncates(self) -> None:
        sections = {
            "a": {"results": [{"chunk_id": "c1", "summary": "x" * 100}, {"chunk_id": "c2", "summary": "y" * 100}]},
        }
        budget = apply_pack_disclosure_budget(sections, global_budget_chars=150)
        self.assertEqual([r["chunk_id"] for r in sections["a"]["results"]], ["c1"])
        self.assertEqual(sections["a"]["disclosure_truncated"], 1)
        self.assertEqual(budget["truncated_chunks"], 1)
        self.assertEqual(budget["used_chars"], 100)

    def test_keeps_at_least_one_per_section_even_if_duplicate(self) -> None:
        # A section whose only candidate is a duplicate still keeps it, so dedup
        # never starves a section of all evidence.
        sections = {
            "a": {"results": [{"chunk_id": "c1", "summary": "x"}]},
            "b": {"results": [{"chunk_id": "c1", "summary": "x"}]},
        }
        apply_pack_disclosure_budget(sections, global_budget_chars=0)
        self.assertEqual([r["chunk_id"] for r in sections["b"]["results"]], ["c1"])
        self.assertEqual(sections["b"]["disclosure_deduped"], 0)


class FocusPackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "FP"]), 0)
        self.broker = ContextBroker("FP")
        for index in range(3):
            self.broker.index_artifact(
                f"CHG-{index:03d}",
                "change",
                Path(f"07_changes/c{index}.md"),
                f"alpha beta change about metric source and target users {index}",
                trace_ids=[f"CHG-{index:03d}"],
                iteration=index + 1,
            )

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_focus_pack_emits_pointers_without_verbatim_body(self) -> None:
        pack = self.broker.build_focus_pack("sync_focus", "alpha beta metric source target users")
        self.assertTrue(pack["pointers"])
        self.assertEqual(pack["count"], len(pack["pointers"]))
        for pointer in pack["pointers"]:
            self.assertIn("read_plan", pointer)
            self.assertIn("summary", pointer)
            # Pointer-only: no verbatim body / content / indexing prefix leaks.
            self.assertNotIn("text", pointer)
            self.assertNotIn("content", pointer)
            self.assertNotIn("context_text", pointer)
        pack_file = Path("workspaces") / "FP" / "08_context_packs" / "sync_focus_focus.json"
        self.assertTrue(pack_file.exists())
        self.assertTrue(pack["path"].endswith("sync_focus_focus.json"))

    def test_focus_pack_degrades_without_error_on_weak_query(self) -> None:
        # A query with no lexical overlap must not raise and must return a valid
        # pack. The exact count is backend-dependent (json-hybrid lexical scoring
        # filters to 0; LanceDB ANN still returns nearest neighbors), so assert the
        # mode-agnostic invariants only.
        pack = self.broker.build_focus_pack("sync_focus", "zzzzz nonexistent vocabulary qqqqq")
        self.assertIsInstance(pack["pointers"], list)
        self.assertEqual(pack["count"], len(pack["pointers"]))
        self.assertTrue(pack["path"].endswith("sync_focus_focus.json"))

    def test_focus_pack_respects_global_budget(self) -> None:
        pack = self.broker.build_focus_pack(
            "sync_focus",
            "alpha beta metric source target users",
            global_budget_chars=10,
        )
        # Budget keeps at least one pointer but trims the rest.
        self.assertGreaterEqual(pack["count"], 1)
        self.assertLessEqual(pack["disclosure_budget"]["used_chars"], 10 + 240)


class NeedsContextGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "NC"]), 0)
        self.broker = ContextBroker("NC")
        for index in range(13):
            self.broker.index_artifact(
                f"REQ-{index:03d}",
                "requirement",
                Path(f"02_requirements/r{index}.md"),
                f"requirement statement number {index} with some body text",
                trace_ids=[f"REQ-{index:03d}"],
            )

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_warns_when_volume_high_and_no_focus_pack(self) -> None:
        result = evaluate_needs_context("NC", indexed_chunks=13)
        self.assertTrue(result["needs_context"])
        self.assertFalse(result["strict"])  # soft by default
        self.assertTrue(result["message"])

    def test_below_threshold_does_not_warn(self) -> None:
        result = evaluate_needs_context("NC", indexed_chunks=3)
        self.assertFalse(result["needs_context"])
        self.assertIsNone(result["message"])

    def test_focus_pack_presence_clears_the_gate(self) -> None:
        self.broker.build_focus_pack("sync_focus", "requirement statement body")
        result = evaluate_needs_context("NC", indexed_chunks=13)
        self.assertTrue(result["has_focus_pack"])
        self.assertFalse(result["needs_context"])

    def test_strict_opt_in_via_config(self) -> None:
        with mock.patch(
            "sentinel.protocols.load_config",
            return_value={"needs_context_gate": {"strict": True}},
        ):
            result = evaluate_needs_context("NC", indexed_chunks=13)
        self.assertTrue(result["strict"])
        self.assertTrue(result["needs_context"])

    def test_health_surfaces_gate_as_soft_warning(self) -> None:
        report = run_health("NC")
        self.assertTrue(any("focus context pack" in w for w in report["warnings"]))
        self.assertFalse(any("focus context pack" in f for f in report["findings"]))
        self.assertIn("needs_context_gate", report)


if __name__ == "__main__":
    unittest.main()
