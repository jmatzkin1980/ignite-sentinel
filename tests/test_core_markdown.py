import os
import tempfile
import unittest
from pathlib import Path

from sentinel.assumptions import assumption_rows
from sentinel.backlog_rollup import collect_story_rows
from sentinel.backlog_status import acceptance_from_story_markdown as story_acceptance_rows
from sentinel.backlog_status import trace_from_frontmatter, update_story_frontmatter
from sentinel.core.markdown import (
    frontmatter_list,
    parse_frontmatter,
    parse_table_rows,
    render_frontmatter,
    table_to_dicts,
    update_frontmatter_keys,
)
from sentinel.discovery import parse_gap_rows
from sentinel.compilers.specs import read_spec_units, spec_unit_statement
from sentinel.generation import parse_ears_requirements
from sentinel.generation import read_spec_units as generation_read_spec_units
from sentinel.generation import spec_unit_statement as generation_spec_unit_statement
from sentinel.health import has_blocking_open_gap
from sentinel.implementation_feedback import acceptance_from_story_markdown as feedback_acceptance_rows
from sentinel.knowledge_ledger import markdown_table_rows
from sentinel.maturity import parse_blocking_gaps, parse_gap_answers, summarize_open_gaps


class CoreMarkdownTests(unittest.TestCase):
    def test_parse_table_rows_matches_tick_stripping_variants(self):
        text = """
| ID | Lens | Status |
| --- | --- | --- |
| `GAP-001` | `Product` | OPEN |
"""
        self.assertEqual(
            parse_table_rows(text),
            [
                ["ID", "Lens", "Status"],
                ["---", "---", "---"],
                ["GAP-001", "Product", "OPEN"],
            ],
        )

    def test_parse_table_rows_can_preserve_code_ticks(self):
        text = "| `AC-001` | Happy Path |\n"
        self.assertEqual(parse_table_rows(text, strip_code_ticks=False), [["`AC-001`", "Happy Path"]])

    def test_parse_table_rows_skips_non_table_lines_by_default(self):
        text = "intro\n| GAP-001 | high | OPEN |\ntrailer"
        self.assertEqual(parse_table_rows(text), [["GAP-001", "high", "OPEN"]])

    def test_parse_table_rows_can_include_legacy_non_table_lines(self):
        text = "intro\n| GAP-001 | high | OPEN |"
        self.assertEqual(
            parse_table_rows(text, require_pipe=False),
            [["intro"], ["GAP-001", "high", "OPEN"]],
        )

    def test_parse_table_rows_can_skip_separator_rows(self):
        text = "| ID | Status |\n| --- | :--- |\n| ASM-001 | ASSUMED |"
        self.assertEqual(
            parse_table_rows(text, skip_separator_rows=True),
            [["ID", "Status"], ["ASM-001", "ASSUMED"]],
        )

    def test_table_to_dicts_uses_first_row_as_header_by_default(self):
        text = "| ID | Status |\n| --- | --- |\n| US-001 | Ready |"
        self.assertEqual(table_to_dicts(text), [{"ID": "US-001", "Status": "Ready"}])

    def test_table_to_dicts_accepts_explicit_headers(self):
        text = "| US-001 | Ready |\n| US-002 | Draft |"
        self.assertEqual(
            table_to_dicts(text, headers=["story_id", "status"]),
            [
                {"story_id": "US-001", "status": "Ready"},
                {"story_id": "US-002", "status": "Draft"},
            ],
        )

    def test_parse_frontmatter_reads_scalars_and_lists(self):
        text = """---
id: SPEC-U-001
status: evidence-backed
trace_ids:
  - REQ-001
  - GAP-001
owner: "Jose"
---
# Body
"""
        self.assertEqual(
            parse_frontmatter(text),
            {
                "id": "SPEC-U-001",
                "status": "evidence-backed",
                "trace_ids": ["REQ-001", "GAP-001"],
                "owner": "Jose",
            },
        )

    def test_parse_frontmatter_requires_closed_block(self):
        self.assertEqual(parse_frontmatter("---\nid: SPEC-U-001\n# Body"), {})
        self.assertEqual(parse_frontmatter("# Body\n---\nid: SPEC-U-001\n---"), {})

    def test_frontmatter_list_matches_existing_renderer(self):
        self.assertEqual(frontmatter_list(["REQ-001", "SPEC-001"]), "  - REQ-001\n  - SPEC-001")

    def test_render_frontmatter_round_trips_supported_subset(self):
        data = {"id": "US-001", "trace": ["REQ-001", "SPEC-001"], "status": "Ready"}
        self.assertEqual(parse_frontmatter(render_frontmatter(data) + "\n# Body"), data)

    def test_update_frontmatter_keys_preserves_existing_order_and_quotes_selected_keys(self):
        text = """---
id: US-001
parent_epic: EPIC-001
status: Draft
trace:
  - REQ-001
---
# Body
"""
        updated = update_frontmatter_keys(text, {"status": "Ready", "owner": "Delivery Lead"}, quote_keys={"owner"})
        self.assertIsNotNone(updated)
        self.assertIn(
            """id: US-001
parent_epic: EPIC-001
status: Ready
owner: "Delivery Lead"
trace:
  - REQ-001""",
            updated,
        )


class MigratedMarkdownCallSiteTests(unittest.TestCase):
    def test_generation_spec_unit_imports_remain_compatible(self):
        self.assertIs(generation_read_spec_units, read_spec_units)
        self.assertIs(generation_spec_unit_statement, spec_unit_statement)

    def test_discovery_gap_rows_keep_tick_stripping_contract(self):
        text = """
| Gap ID | Lens | Severity | Status | Parent | Description | Question | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GAP-001` | product | high | OPEN | REQ-001 | Missing scope | What is in scope? | RAW-001 |
"""
        self.assertEqual(
            parse_gap_rows(text),
            [
                {
                    "id": "GAP-001",
                    "lens": "product",
                    "severity": "high",
                    "status": "OPEN",
                    "parent": "REQ-001",
                    "description": "Missing scope",
                    "question": "What is in scope?",
                    "source": "RAW-001",
                }
            ],
        )

    def test_assumption_rows_keep_tick_stripping_contract(self):
        text = """
| ID | Lens | Statement | Owner | Risk | Justification | Closes Gap | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ASM-001` | technical | Statement | Jose | med | Evidence basis | `GAP-001` | ASSUMED |
"""
        self.assertEqual(
            assumption_rows(text),
            [
                {
                    "id": "ASM-001",
                    "lens": "technical",
                    "statement": "Statement",
                    "owner": "Jose",
                    "risk": "med",
                    "justification": "Evidence basis",
                    "closes_gap": "GAP-001",
                    "status": "ASSUMED",
                }
            ],
        )

    def test_story_acceptance_rows_preserve_code_ticks(self):
        text = "| AC-001 | `happy-path` | Given/When/Then |\n"
        expected = [{"id": "AC-001", "classification": "`happy-path`"}]
        self.assertEqual(story_acceptance_rows(text), expected)
        self.assertEqual(feedback_acceptance_rows(text), expected)

    def test_health_and_maturity_gap_parsers_support_old_and_new_formats(self):
        old_format = "| GAP-001 | high | OPEN | Missing scope |\n"
        new_format = "| GAP-002 | product | high | ANSWERED | REQ-001 | Missing users |\n"
        self.assertTrue(has_blocking_open_gap(old_format + new_format))
        self.assertEqual(parse_blocking_gaps(old_format + new_format, {"critical", "high"}), ["GAP-001", "GAP-002"])
        self.assertEqual(
            summarize_open_gaps(new_format),
            "- `GAP-002` (product, high): Missing users",
        )

    def test_gap_answers_keep_tick_stripping_contract(self):
        text = "| DEC-001 | `GAP-001` | CONFIRMED | Confirmed answer | Client |\n"
        self.assertEqual(parse_gap_answers(text), {"GAP-001": {"statement": "Confirmed answer", "source": "Client"}})

    def test_generation_table_parsers_use_core_markdown(self):
        requirements = """
## Normalized Requirements (EARS)

| ID | Pattern | Statement | Source |
| --- | --- | --- | --- |
| `REQ-EARS-001` | Event-driven | When X, the system shall Y. | RAW-001 |
"""
        self.assertEqual(
            parse_ears_requirements(requirements),
            [
                {
                    "id": "REQ-EARS-001",
                    "pattern": "Event-driven",
                    "statement": "When X, the system shall Y.",
                    "source": "RAW-001",
                }
            ],
        )
        spec_unit = """
## Normalized Requirement

| EARS ID | Statement |
| --- | --- |
| `REQ-EARS-001` | When X, the system shall Y. |
"""
        self.assertEqual(spec_unit_statement(spec_unit), "When X, the system shall Y.")

    def test_knowledge_ledger_table_rows_keep_header_filtering(self):
        text = """
| Seed ID | Lens | Status |
| --- | --- | --- |
| SEED-001 | product | CONFIRMED |
"""
        self.assertEqual(markdown_table_rows(text), [["SEED-001", "product", "CONFIRMED"]])

    def test_frontmatter_call_sites_use_core_parser_contract(self):
        story = """---
id: US-001
parent_epic: EPIC-009
status: Draft
owner: ""
trace:
  - REQ-001
  - SPEC-U-001
---
# US-001 - First slice
"""
        self.assertEqual(trace_from_frontmatter(story), ["REQ-001", "SPEC-U-001"])
        with tempfile.TemporaryDirectory() as temp:
            old_cwd = Path.cwd()
            os.chdir(temp)
            try:
                story_path = Path("workspaces/FRONT/04_backlog/US-001.md")
                story_path.parent.mkdir(parents=True)
                story_path.write_text(story, encoding="utf-8")
                rows = collect_story_rows("FRONT")
                self.assertEqual(rows[0]["epic_id"], "EPIC-009")
                self.assertEqual(rows[0]["status"], "Draft")
                update_story_frontmatter(story_path, "Ready", "Delivery Lead")
                updated = story_path.read_text(encoding="utf-8")
                self.assertIn("status: Ready", updated)
                self.assertIn('owner: "Delivery Lead"', updated)
                self.assertIn("  - REQ-001", updated)
            finally:
                os.chdir(old_cwd)

    def test_spec_unit_frontmatter_lists_are_read_by_core_parser(self):
        unit = """---
id: SPEC-U-001
status: evidence-backed
trace_ids:
  - REQ-001
ears:
  - REQ-EARS-001
sources:
  - 02_requirements/requirements.md#normalized-requirements-ears
---
# SPEC-U-001 - Requirement

## Normalized Requirement

| EARS ID | Statement |
| --- | --- |
| REQ-EARS-001 | When X, the system shall Y. |
"""
        with tempfile.TemporaryDirectory() as temp:
            old_cwd = Path.cwd()
            os.chdir(temp)
            try:
                unit_path = Path("workspaces/FRONT/03_specs/units/SPEC-U-001.md")
                unit_path.parent.mkdir(parents=True)
                unit_path.write_text(unit, encoding="utf-8")
                units = read_spec_units("FRONT")
                self.assertEqual(units[0]["trace_ids"], ["REQ-001"])
                self.assertEqual(units[0]["ears"], ["REQ-EARS-001"])
                self.assertEqual(
                    units[0]["sources"],
                    ["02_requirements/requirements.md#normalized-requirements-ears"],
                )
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
