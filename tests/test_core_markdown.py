import unittest

from sentinel.core.markdown import (
    frontmatter_list,
    parse_frontmatter,
    parse_table_rows,
    render_frontmatter,
    table_to_dicts,
)


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


if __name__ == "__main__":
    unittest.main()
