"""Tests for IMP-049 declarative backlog slicing model."""
from __future__ import annotations

import unittest

from sentinel.generation import (
    render_enabler_boundary,
    render_slicing_strategy_table,
    slicing_decision_for_spec_unit,
)
from sentinel.slicing_model import load_slicing_model


EXPECTED_STRATEGY_TABLE = """| Heuristic | How Sentinel Applies It |
| --- | --- |
| Product Backlog transparency | Items stay ordered, explicit and inspectable against the product goal. |
| INVEST | Stories must be independent enough to plan, valuable, small enough for a sprint-sized increment, and testable. |
| Vertical slicing | Prefer slices that cross user experience, behavior, data, and validation. Avoid frontend-only/backend-only stories as the default. |
| SPIDR | Use Spikes for uncertainty, Paths for alternate flows, Interfaces for surfaces, Data for source variations, Rules for business constraints. |
| Lawrence patterns | Reduce variation to the smallest useful version first, then add workflow steps, edge cases, performance or external dependency work. |
| Small but valuable | Do not split below the value boundary. A small story must still be independently meaningful, testable, and useful. |
| Cross-cutting enablers | Only create enabler backlog when implementation work must be built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces. Generic environment or accessibility setup is a precondition, not an enabler story. |
| Agent readiness | Give downstream agents bounded context, domain evidence, autonomy limits, validation contract, non-goals, dependencies, blast radius and stop conditions. |"""

EXPECTED_ENABLER_BOUNDARY = """Use a separate enabler epic only when the work is specifically required to support project functionality across multiple stories, epics, FRs, or implementation surfaces. Valid enablers name the capability boundary they support, the risk or dependency they reduce, the reason they must be built earlier, and the objective evidence that proves completion.

Reject loose items such as "make an internal tool accessible", generic environment setup, broad infrastructure hardening, or unspecified backend/frontend preparation unless they are tied to this project's confirmed functionality and have implementation evidence."""


class SlicingModelTests(unittest.TestCase):
    def test_declarative_model_renders_existing_strategy_and_boundary_text(self):
        model = load_slicing_model()

        self.assertEqual(render_slicing_strategy_table(model), EXPECTED_STRATEGY_TABLE)
        self.assertEqual(render_enabler_boundary(model), EXPECTED_ENABLER_BOUNDARY)

    def test_override_model_can_change_strategy_without_python_changes(self):
        model = load_slicing_model(
            override={
                "strategy_rows": [{"heuristic": "INVEST", "applies": "Keep the team rule visible."}],
                "enabler_boundary": {"paragraphs": ["Boundary paragraph one.", "Boundary paragraph two."]},
                "patterns": [
                    {
                        "id": "workflow",
                        "slicing": "Workflow Step / Happy Path",
                        "rationale": "Fallback.",
                        "priority": 1,
                        "tokens": [],
                    }
                ],
            }
        )

        self.assertIn("Keep the team rule visible", render_slicing_strategy_table(model))
        self.assertEqual(render_enabler_boundary(model), "Boundary paragraph one.\n\nBoundary paragraph two.")

    def test_spec_unit_shape_selects_existing_slicing_pattern_with_rationale(self):
        model = load_slicing_model()

        data_decision = slicing_decision_for_spec_unit(
            {
                "id": "SPEC-U-005",
                "statement": "If the metrics service is unavailable, then the system shall show risk status unknown.",
                "pattern": "unwanted",
                "title": "SPEC-U-005",
            },
            model,
        )
        rule_decision = slicing_decision_for_spec_unit(
            {
                "id": "SPEC-U-002",
                "statement": "When a case breaches SLA, the system shall flag the queue as high risk.",
                "pattern": "event-driven",
                "title": "SPEC-U-002",
            },
            model,
        )

        self.assertEqual(data_decision["slicing"], "Data / External Dependency")
        self.assertIn("SPEC-U-005", data_decision["rationale"])
        self.assertEqual(rule_decision["slicing"], "Rules / Regression Slice")
        self.assertIn("SPIDR Rules", rule_decision["rationale"])


if __name__ == "__main__":
    unittest.main()
